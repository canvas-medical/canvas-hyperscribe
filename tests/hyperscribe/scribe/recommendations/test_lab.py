from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    NoteSection,
    Transcript,
    TranscriptItem,
)
from hyperscribe.scribe.recommendations.lab import (
    LabRecommender,
    _build_aoe_payload,
    _build_pass1_user_prompt,
    _build_pass2_user_prompt,
    _format_transcript,
    _resolve_lab_partner,
    _resolve_tests,
)
from hyperscribe.scribe.recommendations.schemas import (
    AoeAnswer,
    LabTestEntry,
)


# ---------- helpers ----------


def _make_partner(
    *,
    name: str = "Generic Lab",
    dbid: int = 1,
    id: str = "11111111-1111-1111-1111-111111111111",
) -> MagicMock:
    partner = MagicMock()
    partner.name = name
    partner.dbid = dbid
    partner.id = id
    partner.active = True
    partner.electronic_ordering_enabled = True
    return partner


def _make_test(
    *,
    dbid: int,
    order_code: str,
    order_name: str,
    keywords: str = "",
) -> MagicMock:
    test = MagicMock()
    test.dbid = dbid
    test.order_code = order_code
    test.order_name = order_name
    test.keywords = keywords
    return test


def _make_question(
    *,
    code: str,
    body: str,
    qtype: str = "text",
    required: bool = False,
    lab_partner_test: MagicMock | None = None,
    choices: list[tuple[str, str]] | None = None,
) -> MagicMock:
    question = MagicMock()
    question.code = code
    question.body = body
    question.type = qtype
    question.required = required
    question.lab_partner_test = lab_partner_test
    choice_mocks: list[MagicMock] = []
    for label, value in choices or []:
        choice = MagicMock()
        choice.label = label
        choice.value = value
        choice_mocks.append(choice)
    question.choices.all.return_value = choice_mocks
    return question


def _make_note(sections: list[NoteSection] | None = None) -> ClinicalNote:
    return ClinicalNote(title="Test", sections=sections or [])


def _make_client(payloads: list[dict[str, Any]] | None = None) -> MagicMock:
    """Build a mock LLM client whose .request() returns the given payloads in order."""
    client = MagicMock()
    if payloads is not None:
        responses = [
            LlmResponse(
                code=HTTPStatus.OK,
                response=json.dumps(p),
                tokens=LlmTokens(prompt=100, generated=50),
            )
            for p in payloads
        ]
        client.request.side_effect = responses
    return client


def _patch_partner_resolution(
    *,
    preferred_value: str | None,
    name_match: MagicMock | None,
    fallback: MagicMock | None,
):
    """Build patches for PracticeLocationSetting + LabPartner used by _resolve_lab_partner."""
    setting_qs = MagicMock()
    if preferred_value is None:
        setting_qs.first.return_value = None
    else:
        setting = MagicMock()
        setting.value = preferred_value
        setting_qs.first.return_value = setting

    partner_objects = MagicMock()

    def filter_side_effect(**kwargs: Any) -> MagicMock:
        # Two filters: by-name (specific) and fallback (no name)
        result = MagicMock()
        if "name" in kwargs:
            result.first.return_value = name_match
        else:
            result.first.return_value = fallback
        return result

    partner_objects.filter.side_effect = filter_side_effect

    return (
        patch(
            "hyperscribe.scribe.recommendations.lab.PracticeLocationSetting.objects",
            MagicMock(filter=MagicMock(return_value=setting_qs)),
        ),
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartner.objects",
            partner_objects,
        ),
    )


# ---------- _resolve_lab_partner ----------


def test_resolve_lab_partner_preferred_found() -> None:
    """Preferred setting resolves to a matching active electronic-ordering partner."""
    matched = _make_partner(name="Quest")
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Quest",
        name_match=matched,
        fallback=None,
    )
    with p_setting, p_partner:
        result = _resolve_lab_partner()
    assert result is matched


def test_resolve_lab_partner_preferred_not_in_catalog_falls_back() -> None:
    """Preferred name doesn't match a partner; fallback to first electronic-enabled partner."""
    fallback = _make_partner(name="Generic Lab")
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Stale Lab",
        name_match=None,
        fallback=fallback,
    )
    with p_setting, p_partner:
        result = _resolve_lab_partner()
    assert result is fallback


def test_resolve_lab_partner_no_preferred_uses_fallback() -> None:
    fallback = _make_partner(name="Generic Lab")
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value=None,
        name_match=None,
        fallback=fallback,
    )
    with p_setting, p_partner:
        result = _resolve_lab_partner()
    assert result is fallback


def test_resolve_lab_partner_none_available() -> None:
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value=None,
        name_match=None,
        fallback=None,
    )
    with p_setting, p_partner:
        result = _resolve_lab_partner()
    assert result is None


# ---------- _resolve_tests ----------


def test_resolve_tests_keyword_match() -> None:
    partner = _make_partner()
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    with patch(
        "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
        MagicMock(filter=MagicMock(return_value=filter_initial)),
    ):
        result = _resolve_tests(
            partner,
            [LabTestEntry(name="Complete Blood Count", keywords="CBC, hemogram")],
        )
    assert result == [cbc]


def test_resolve_tests_no_match_drops_test() -> None:
    partner = _make_partner()
    chained = MagicMock()
    chained.first.return_value = None
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    with patch(
        "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
        MagicMock(filter=MagicMock(return_value=filter_initial)),
    ):
        result = _resolve_tests(
            partner,
            [LabTestEntry(name="Unicorn Tears Panel", keywords="UTP, mythical")],
        )
    assert result == []


def test_resolve_tests_cache_reuse_across_entries() -> None:
    """Same keyword should hit the DB once, even across multiple entries."""
    partner = _make_partner()
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    with patch(
        "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
        MagicMock(filter=MagicMock(return_value=filter_initial)),
    ) as mock_objects:
        cache: dict[str, Any] = {}
        _resolve_tests(
            partner,
            [LabTestEntry(name="Complete Blood Count", keywords="CBC")],
            cache,
        )
        _resolve_tests(
            partner,
            [LabTestEntry(name="Complete Blood Count", keywords="CBC")],
            cache,
        )

    # First entry: tries "Complete Blood Count" — hits and breaks. So one DB call across both runs.
    assert mock_objects.filter.call_count == 1


def test_resolve_tests_partial_match_in_one_order() -> None:
    """Some tests in the entry list resolve, some don't; resolved ones are returned."""
    partner = _make_partner()
    cmp_test = _make_test(dbid=20, order_code="CMP", order_name="Comprehensive Metabolic Panel")

    chained_hit = MagicMock()
    chained_hit.first.return_value = cmp_test
    filter_hit = MagicMock()
    filter_hit.filter.return_value = chained_hit

    chained_miss = MagicMock()
    chained_miss.first.return_value = None
    filter_miss = MagicMock()
    filter_miss.filter.return_value = chained_miss

    objects_mock = MagicMock()
    # Each call to filter(lab_partner=...) returns a fresh chain; we alternate.
    objects_mock.filter.side_effect = [filter_miss, filter_miss, filter_hit, filter_hit]

    with patch(
        "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
        objects_mock,
    ):
        result = _resolve_tests(
            partner,
            [
                LabTestEntry(name="Made Up Test", keywords="MUT"),
                LabTestEntry(name="Comprehensive Metabolic Panel", keywords="CMP"),
            ],
        )
    assert result == [cmp_test]


# ---------- formatting helpers ----------


def test_format_transcript_basic() -> None:
    transcript = Transcript(
        items=[
            TranscriptItem(text="Let's get a CBC.", speaker="provider", start_offset_ms=0, end_offset_ms=1000),
            TranscriptItem(text="Okay.", speaker="patient", start_offset_ms=1100, end_offset_ms=1500),
        ]
    )
    result = _format_transcript(transcript)
    assert "Provider: Let's get a CBC." in result
    assert "Patient: Okay." in result


def test_format_transcript_unknown_speaker() -> None:
    transcript = Transcript(
        items=[
            TranscriptItem(text="hi", speaker="", start_offset_ms=0, end_offset_ms=100),
        ]
    )
    assert "Unknown: hi" in _format_transcript(transcript)


def test_build_pass1_user_prompt() -> None:
    sections = [
        NoteSection(key="assessment_and_plan", title="A&P", text="Order CBC and CMP."),
        NoteSection(key="plan", title="Plan", text="Lipid panel."),
    ]
    result = _build_pass1_user_prompt(sections)
    assert "## A&P" in result
    assert "Order CBC and CMP." in result
    assert "## Plan" in result
    assert "Lipid panel." in result


def test_build_pass2_user_prompt_includes_questions_and_choices() -> None:
    test = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")
    q1 = _make_question(
        code="FAST",
        body="Was the patient fasting?",
        qtype="select",
        required=True,
        lab_partner_test=test,
        choices=[("Yes", "Y"), ("No", "N")],
    )
    test_questions = {"CBC": ("Complete Blood Count", [q1])}
    result = _build_pass2_user_prompt("Provider: fasting since 8pm", test_questions)
    assert "## Transcript" in result
    assert "fasting since 8pm" in result
    assert "Complete Blood Count" in result
    assert "FAST" in result
    assert "Was the patient fasting?" in result
    assert "label: Yes, value: Y" in result


# ---------- _build_aoe_payload ----------


def _make_aoe_answer(*, test_order_code: str, question_code: str, answer: str, confidence: str) -> AoeAnswer:
    """Build an AoeAnswer via the camelCase aliases that BaseModelLlmJson uses."""
    return AoeAnswer.model_validate(
        {
            "testOrderCode": test_order_code,
            "questionCode": question_code,
            "answer": answer,
            "confidence": confidence,
        },
    )


def test_build_aoe_payload_with_select_label_lookup() -> None:
    test = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")
    question = _make_question(
        code="FAST",
        body="Was the patient fasting?",
        qtype="select",
        required=True,
        lab_partner_test=test,
        choices=[("Yes", "Y"), ("No", "N")],
    )
    test_questions = {"CBC": ("Complete Blood Count", [question])}
    answers_by_key = {
        ("CBC", "FAST"): _make_aoe_answer(
            test_order_code="CBC",
            question_code="FAST",
            answer="Y",
            confidence="high",
        ),
    }
    aoe, missing = _build_aoe_payload([test], test_questions, answers_by_key)
    assert len(aoe) == 1
    assert aoe[0]["answer_value"] == "Y"
    assert aoe[0]["answer_label"] == "Yes"
    assert aoe[0]["question_body"] == "Was the patient fasting?"
    assert aoe[0]["confidence"] == "high"
    assert missing == []


def test_build_aoe_payload_required_without_answer_appears_in_missing() -> None:
    test = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")
    required_q = _make_question(code="FAST", body="Fasting?", qtype="select", required=True, lab_partner_test=test)
    optional_q = _make_question(code="LMP", body="LMP date", qtype="date", required=False, lab_partner_test=test)
    test_questions = {"CBC": ("Complete Blood Count", [required_q, optional_q])}
    aoe, missing = _build_aoe_payload([test], test_questions, {})
    assert aoe == []
    assert len(missing) == 1
    assert missing[0]["question_code"] == "FAST"


def test_build_aoe_payload_text_question_no_label() -> None:
    test = _make_test(dbid=10, order_code="LIPID", order_name="Lipid Panel")
    question = _make_question(code="NOTES", body="Other notes", qtype="text", required=False, lab_partner_test=test)
    test_questions = {"LIPID": ("Lipid Panel", [question])}
    answers_by_key = {
        ("LIPID", "NOTES"): _make_aoe_answer(
            test_order_code="LIPID",
            question_code="NOTES",
            answer="Recent statin start",
            confidence="medium",
        ),
    }
    aoe, missing = _build_aoe_payload([test], test_questions, answers_by_key)
    assert len(aoe) == 1
    assert aoe[0]["answer_value"] == "Recent statin start"
    assert aoe[0]["answer_label"] is None
    assert aoe[0]["confidence"] == "medium"


# ---------- LabRecommender.recommend ----------


def test_recommend_skips_when_no_relevant_sections() -> None:
    note = _make_note([NoteSection(key="social_history", title="Social", text="Non-smoker")])
    client = _make_client()
    assert LabRecommender().recommend(note, client) == []
    client.request.assert_not_called()


def test_recommend_skips_when_no_lab_partner() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order labs")])
    client = _make_client()
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value=None,
        name_match=None,
        fallback=None,
    )
    with p_setting, p_partner:
        assert LabRecommender().recommend(note, client) == []
    client.request.assert_not_called()


def test_recommend_pass1_llm_error_returns_empty() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="boom",
        tokens=LlmTokens(prompt=0, generated=0),
    )
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=_make_partner(),
        fallback=None,
    )
    with p_setting, p_partner:
        assert LabRecommender().recommend(note, client) == []


def test_recommend_pass1_exception_returns_empty() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    client = MagicMock()
    client.request.side_effect = Exception("network down")
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=_make_partner(),
        fallback=None,
    )
    with p_setting, p_partner:
        assert LabRecommender().recommend(note, client) == []


def test_recommend_pass1_malformed_json_returns_empty() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not json",
        tokens=LlmTokens(prompt=0, generated=0),
    )
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=_make_partner(),
        fallback=None,
    )
    with p_setting, p_partner:
        assert LabRecommender().recommend(note, client) == []


def test_recommend_no_orders_in_pass1() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Continue meds")])
    client = _make_client([{"orders": []}])
    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=_make_partner(),
        fallback=None,
    )
    with p_setting, p_partner:
        assert LabRecommender().recommend(note, client) == []


def test_recommend_no_test_resolves_returns_empty() -> None:
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order made-up test")])
    client = _make_client(
        [
            {
                "orders": [
                    {
                        "tests": [{"name": "Made Up Test", "keywords": "MUT"}],
                        "fastingRequired": False,
                        "comment": None,
                        "reason": "test",
                    },
                ],
            },
        ]
    )
    partner = _make_partner()

    chained = MagicMock()
    chained.first.return_value = None
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=partner,
        fallback=None,
    )
    with (
        p_setting,
        p_partner,
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
            MagicMock(filter=MagicMock(return_value=filter_initial)),
        ),
    ):
        assert LabRecommender().recommend(note, client) == []


def test_recommend_happy_path_no_aoe_no_transcript() -> None:
    """Single order, single test, no AOE questions, no transcript — basic proposal."""
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    client = _make_client(
        [
            {
                "orders": [
                    {
                        "tests": [{"name": "Complete Blood Count", "keywords": "CBC"}],
                        "fastingRequired": False,
                        "comment": "fasting OK",
                        "reason": "screening",
                    },
                ],
            },
        ]
    )
    partner = _make_partner(name="Generic Lab")
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    qs_filter = MagicMock()
    qs_filter.prefetch_related.return_value = []
    qs_mock = MagicMock()
    qs_mock.filter.return_value = qs_filter

    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=partner,
        fallback=None,
    )
    with (
        p_setting,
        p_partner,
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
            MagicMock(filter=MagicMock(return_value=filter_initial)),
        ),
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTestQuestion.objects",
            qs_mock,
        ),
    ):
        proposals = LabRecommender().recommend(note, client)

    assert len(proposals) == 1
    p = proposals[0]
    assert p.command_type == "lab_order"
    assert p.display == "Complete Blood Count"
    assert p.data["lab_partner"] == "11111111-1111-1111-1111-111111111111"
    assert p.data["lab_partner_name"] == "Generic Lab"
    assert p.data["tests_order_codes"] == ["CBC"]
    assert p.data["test_names"] == ["Complete Blood Count"]
    assert p.data["diagnosis_displays"] == []
    assert p.data["fasting_required"] is False
    assert p.data["comment"] == "fasting OK"
    assert p.data["diagnosis_codes"] == []
    assert p.data["aoe_answers"] == []
    assert p.data["missing_required_aoes"] == []
    assert p.data["reason"] == "screening"


def test_recommend_with_aoe_extracted_from_transcript() -> None:
    """End-to-end: pass 1 finds CBC, pass 2 fills the FASTING AOE from transcript."""
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC, fasting")])
    transcript = Transcript(
        items=[
            TranscriptItem(
                text="She's been fasting since 8pm last night.",
                speaker="provider",
                start_offset_ms=0,
                end_offset_ms=2000,
            ),
        ]
    )
    client = _make_client(
        [
            # Pass 1
            {
                "orders": [
                    {
                        "tests": [{"name": "Complete Blood Count", "keywords": "CBC"}],
                        "fastingRequired": True,
                        "comment": None,
                        "reason": "annual",
                    },
                ],
            },
            # Pass 2
            {
                "answers": [
                    {
                        "testOrderCode": "CBC",
                        "questionCode": "FAST",
                        "answer": "Y",
                        "confidence": "high",
                    },
                    # Low-confidence answer should be dropped
                    {
                        "testOrderCode": "CBC",
                        "questionCode": "OTHER",
                        "answer": "?",
                        "confidence": "low",
                    },
                ],
            },
        ]
    )

    partner = _make_partner(name="Generic Lab")
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")
    fasting_q = _make_question(
        code="FAST",
        body="Was the patient fasting?",
        qtype="select",
        required=True,
        lab_partner_test=cbc,
        choices=[("Yes", "Y"), ("No", "N")],
    )
    other_q = _make_question(
        code="OTHER",
        body="Other notes",
        qtype="text",
        required=False,
        lab_partner_test=cbc,
    )

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    qs_filter = MagicMock()
    qs_filter.prefetch_related.return_value = [fasting_q, other_q]
    qs_mock = MagicMock()
    qs_mock.filter.return_value = qs_filter

    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=partner,
        fallback=None,
    )
    with (
        p_setting,
        p_partner,
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
            MagicMock(filter=MagicMock(return_value=filter_initial)),
        ),
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTestQuestion.objects",
            qs_mock,
        ),
    ):
        proposals = LabRecommender().recommend(note, client, transcript=transcript)

    assert len(proposals) == 1
    data = proposals[0].data
    assert data["fasting_required"] is True
    assert len(data["aoe_answers"]) == 1
    assert data["aoe_answers"][0]["question_code"] == "FAST"
    assert data["aoe_answers"][0]["answer_value"] == "Y"
    assert data["aoe_answers"][0]["answer_label"] == "Yes"
    assert data["aoe_answers"][0]["confidence"] == "high"
    assert data["missing_required_aoes"] == []  # FAST is required and was filled


def test_recommend_pass2_skipped_when_no_questions() -> None:
    """If no resolved test has AOE questions, pass 2 is not invoked."""
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    transcript = Transcript(
        items=[
            TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100),
        ]
    )
    client = _make_client(
        [
            {
                "orders": [
                    {
                        "tests": [{"name": "Complete Blood Count", "keywords": "CBC"}],
                        "fastingRequired": False,
                        "comment": None,
                        "reason": "test",
                    },
                ],
            },
        ]
    )
    partner = _make_partner()
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    qs_filter = MagicMock()
    qs_filter.prefetch_related.return_value = []
    qs_mock = MagicMock()
    qs_mock.filter.return_value = qs_filter

    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=partner,
        fallback=None,
    )
    with (
        p_setting,
        p_partner,
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
            MagicMock(filter=MagicMock(return_value=filter_initial)),
        ),
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTestQuestion.objects",
            qs_mock,
        ),
    ):
        proposals = LabRecommender().recommend(note, client, transcript=transcript)

    # Only one LLM request should have been made (pass 1)
    assert client.request.call_count == 1
    assert len(proposals) == 1
    assert proposals[0].data["aoe_answers"] == []


def test_recommend_pass2_error_still_emits_proposal() -> None:
    """If AOE pass 2 errors, the proposal is still emitted with empty aoe_answers and required marked missing."""
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    transcript = Transcript(
        items=[
            TranscriptItem(text="anything", speaker="provider", start_offset_ms=0, end_offset_ms=100),
        ]
    )

    client = MagicMock()
    pass1 = LlmResponse(
        code=HTTPStatus.OK,
        response=json.dumps(
            {
                "orders": [
                    {
                        "tests": [{"name": "Complete Blood Count", "keywords": "CBC"}],
                        "fastingRequired": False,
                        "comment": None,
                        "reason": "screening",
                    },
                ],
            }
        ),
        tokens=LlmTokens(prompt=0, generated=0),
    )
    client.request.side_effect = [pass1, Exception("pass 2 failure")]

    partner = _make_partner()
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")
    required_q = _make_question(
        code="FAST",
        body="Fasting?",
        qtype="select",
        required=True,
        lab_partner_test=cbc,
        choices=[("Yes", "Y"), ("No", "N")],
    )

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    qs_filter = MagicMock()
    qs_filter.prefetch_related.return_value = [required_q]
    qs_mock = MagicMock()
    qs_mock.filter.return_value = qs_filter

    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=partner,
        fallback=None,
    )
    with (
        p_setting,
        p_partner,
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
            MagicMock(filter=MagicMock(return_value=filter_initial)),
        ),
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTestQuestion.objects",
            qs_mock,
        ),
    ):
        proposals = LabRecommender().recommend(note, client, transcript=transcript)

    assert len(proposals) == 1
    data = proposals[0].data
    assert data["aoe_answers"] == []
    assert len(data["missing_required_aoes"]) == 1
    assert data["missing_required_aoes"][0]["question_code"] == "FAST"


def test_recommend_no_transcript_skips_pass2_marks_required_missing() -> None:
    """No transcript = no AOE pass 2; required AOEs end up in missing_required_aoes."""
    note = _make_note([NoteSection(key="plan", title="Plan", text="Order CBC")])
    client = _make_client(
        [
            {
                "orders": [
                    {
                        "tests": [{"name": "Complete Blood Count", "keywords": "CBC"}],
                        "fastingRequired": False,
                        "comment": None,
                        "reason": "screen",
                    },
                ],
            },
        ]
    )
    partner = _make_partner()
    cbc = _make_test(dbid=10, order_code="CBC", order_name="Complete Blood Count")
    required_q = _make_question(
        code="FAST",
        body="Fasting?",
        qtype="select",
        required=True,
        lab_partner_test=cbc,
    )

    chained = MagicMock()
    chained.first.return_value = cbc
    filter_initial = MagicMock()
    filter_initial.filter.return_value = chained

    qs_filter = MagicMock()
    qs_filter.prefetch_related.return_value = [required_q]
    qs_mock = MagicMock()
    qs_mock.filter.return_value = qs_filter

    p_setting, p_partner = _patch_partner_resolution(
        preferred_value="Generic Lab",
        name_match=partner,
        fallback=None,
    )
    with (
        p_setting,
        p_partner,
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTest.objects",
            MagicMock(filter=MagicMock(return_value=filter_initial)),
        ),
        patch(
            "hyperscribe.scribe.recommendations.lab.LabPartnerTestQuestion.objects",
            qs_mock,
        ),
    ):
        proposals = LabRecommender().recommend(note, client, transcript=None)

    # Only pass 1 was called, no pass 2
    assert client.request.call_count == 1
    assert len(proposals) == 1
    assert proposals[0].data["aoe_answers"] == []
    assert len(proposals[0].data["missing_required_aoes"]) == 1
