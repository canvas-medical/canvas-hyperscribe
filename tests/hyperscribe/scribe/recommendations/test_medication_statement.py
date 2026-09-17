from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection, Transcript, TranscriptItem
from hyperscribe.scribe.recommendations.medication_statement import (
    MedicationRecommender,
    _build_user_prompt,
    _resolve_medication,
)


def _make_note(sections: list[NoteSection] | None = None) -> ClinicalNote:
    return ClinicalNote(title="Test Note", sections=sections or [])


def _make_client(response_data: dict | None = None, code: HTTPStatus = HTTPStatus.OK) -> MagicMock:
    client = MagicMock()
    if response_data is not None:
        client.request.return_value = LlmResponse(
            code=code,
            response=json.dumps(response_data),
            tokens=LlmTokens(prompt=100, generated=50),
        )
    return client


def test_build_user_prompt() -> None:
    sections = [
        NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg daily"),
        NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Start metformin."),
    ]
    result = _build_user_prompt(sections)
    assert "## Current Medications" in result
    assert "Lisinopril 10mg daily" in result
    assert "## Assessment & Plan" in result


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_found(mock_details: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_details.return_value = [
        MedicationDetail(fdb_code="12345", description="Lisinopril 10mg Tablet", quantities=[]),
    ]
    result = _resolve_medication("Lisinopril 10mg", "lisinopril, lisinopril 10mg")
    assert result is not None
    assert result.fdb_code == "12345"
    assert result.description == "Lisinopril 10mg Tablet"
    # the full medication name is searched first so FDB returns the stated strength
    mock_details.assert_called_once_with(["Lisinopril 10mg"])


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_matches_stated_strength(mock_details: MagicMock) -> None:
    """Regression: a 20 mg statement must not resolve to the 10 mg group."""
    from hyperscribe.structures.medication_detail import MedicationDetail

    # FDB returns the 10 mg group first, then the 20 mg group.
    mock_details.return_value = [
        MedicationDetail(fdb_code="10", description="Lisinopril 10 mg Tablet", quantities=[]),
        MedicationDetail(fdb_code="20", description="Lisinopril 20 mg Tablet", quantities=[]),
    ]
    result = _resolve_medication("Lisinopril 20 mg", "lisinopril")
    assert result is not None
    assert result.fdb_code == "20"
    assert result.description == "Lisinopril 20 mg Tablet"


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_returns_none_when_no_strength_match(mock_details: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_details.return_value = [
        MedicationDetail(fdb_code="10", description="Lisinopril 10 mg Tablet", quantities=[]),
        MedicationDetail(fdb_code="40", description="Lisinopril 40 mg Tablet", quantities=[]),
    ]
    # stated strength (5 mg) is not in the candidate set -> None (fail-safe),
    # so the proposal keeps the medication text without a wrong-strength FDB code
    assert _resolve_medication("Lisinopril 5 mg", "lisinopril") is None


@patch("hyperscribe.scribe.recommendations._medication_match.CanvasScience.medication_details")
def test_resolve_medication_not_found(mock_details: MagicMock) -> None:
    mock_details.return_value = []
    result = _resolve_medication("xyznonexistent 5mg", "xyznonexistent")
    assert result is None


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_success(mock_resolve: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_resolve.return_value = MedicationDetail(fdb_code="12345", description="Lisinopril 10mg Tablet", quantities=[])

    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg daily"),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 10mg", "sig": "Take 1 tablet daily", "keywords": "lisinopril"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].command_type == "medication_statement"
    assert proposals[0].display == "Lisinopril 10mg Tablet"
    assert proposals[0].data["medication_text"] == "Lisinopril 10mg Tablet"
    assert proposals[0].data["sig"] == "Take 1 tablet daily"
    assert proposals[0].data["fdb_code"]["system"] == "http://www.fdbhealth.com/"
    assert proposals[0].data["fdb_code"]["code"] == "12345"
    assert proposals[0].data["fdb_code"]["display"] == "Lisinopril 10mg Tablet"
    assert proposals[0].section_key == "_recommended"

    client.reset_prompts.assert_called_once()
    client.set_schema.assert_called_once()


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_no_fdb_match(mock_resolve: MagicMock) -> None:
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- SomeDrug 5mg daily"),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "SomeDrug 5mg", "sig": "Take daily", "keywords": "somedrug"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["fdb_code"] is None
    assert proposals[0].data["medication_text"] == "SomeDrug 5mg"


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_blanks_placeholder_sig(mock_resolve: MagicMock) -> None:
    """A medication with no stated directions surfaces a blank sig, not "<UNKNOWN>"."""
    mock_resolve.return_value = None

    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 20mg"),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 20mg", "sig": "<UNKNOWN>", "keywords": "lisinopril"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 1
    assert proposals[0].data["sig"] == ""


def test_recommend_empty_note() -> None:
    note = _make_note(
        [
            NoteSection(key="social_history", title="Social History", text="Non-smoker"),
        ]
    )
    client = _make_client()

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []
    client.request.assert_not_called()


def test_recommend_llm_error() -> None:
    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg"),
        ]
    )
    client = _make_client(code=HTTPStatus.INTERNAL_SERVER_ERROR, response_data={"error": "fail"})
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_llm_exception() -> None:
    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg"),
        ]
    )
    client = MagicMock()
    client.request.side_effect = Exception("Network error")

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


def test_recommend_malformed_response() -> None:
    note = _make_note(
        [
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg"),
        ]
    )
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert proposals == []


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_multiple_medications(mock_resolve: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_resolve.side_effect = [
        MedicationDetail(fdb_code="111", description="Lisinopril 10mg", quantities=[]),
        MedicationDetail(fdb_code="222", description="Metformin 500mg", quantities=[]),
    ]

    note = _make_note(
        [
            NoteSection(
                key="current_medications",
                title="Current Medications",
                text="- Lisinopril 10mg daily\n- Metformin 500mg BID",
            ),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 10mg", "sig": "Take daily", "keywords": "lisinopril"},
                {"medicationName": "Metformin 500mg", "sig": "Take twice daily", "keywords": "metformin"},
            ]
        }
    )

    recommender = MedicationRecommender()
    proposals = recommender.recommend(note, client)

    assert len(proposals) == 2
    assert proposals[0].display == "Lisinopril 10mg"
    assert proposals[0].data["fdb_code"]["code"] == "111"
    assert proposals[1].display == "Metformin 500mg"
    assert proposals[1].data["fdb_code"]["code"] == "222"


# ── KOALA-6644: PRN recovery from the transcript ─────────────────────────
#
# Nabla's note-generation step drops as-needed medications, and the loss rate rises with the
# number of PRNs dictated. Since extraction read only the generated note, a dropped PRN was
# unrecoverable and nothing errored. These cover the transcript fallback.


def _prn_transcript() -> Transcript:
    """A transcript dictating six PRN medications, as in the ticket's confirmed case."""
    dictated = [
        "lorazepam 0.5 mg every four hours as needed for anxiety or agitation",
        "acetaminophen 650 mg as needed for pain",
        "ondansetron 4 mg as needed for nausea",
        "albuterol two puffs as needed for shortness of breath",
        "melatonin 3 mg as needed at bedtime",
        "polyethylene glycol 17 g as needed for constipation",
    ]
    return Transcript(
        items=[
            TranscriptItem(
                text=text,
                speaker="doctor",
                start_offset_ms=60_000 + i * 10_000,
                end_offset_ms=65_000 + i * 10_000,
            )
            for i, text in enumerate(dictated)
        ]
    )


def _note_with_scheduled_lorazepam_only() -> ClinicalNote:
    """The generated note as Nabla produced it: a scheduled dose, none of the PRNs.

    Mirrors note dbid 119673 — lorazepam appears, but as the patient's scheduled pre-shower
    dose rather than the dictated as-needed order.
    """
    return _make_note(
        [
            NoteSection(
                key="current_medications",
                title="Meds Discussed",
                text="- Lorazepam: one tablet daily, one hour before showers on Mondays and Wednesdays only",
            ),
        ]
    )


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_sends_prn_transcript_windows_to_the_llm(mock_resolve: MagicMock) -> None:
    """As-needed transcript excerpts and the PRN instructions reach the model."""
    mock_resolve.return_value = None
    client = _make_client({"medications": []})

    MedicationRecommender().recommend(_note_with_scheduled_lorazepam_only(), client, transcript=_prn_transcript())

    user_prompt = client.set_user_prompt.call_args[0][0][0]
    system_prompt = client.set_system_prompt.call_args[0][0][0]
    assert "## Transcript Excerpts (as-needed medication language detected)" in user_prompt
    assert "every four hours as needed for anxiety or agitation" in user_prompt
    # the note is still supplied — the transcript augments it, never replaces it
    assert "one hour before showers" in user_prompt
    assert "SAME DRUG, TWO ORDERS" in system_prompt
    assert "from_transcript=true" in system_prompt


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_without_transcript_omits_prn_instructions(mock_resolve: MagicMock) -> None:
    """No transcript means the prompt is exactly what it was before PRN recovery existed."""
    mock_resolve.return_value = None
    client = _make_client({"medications": []})

    MedicationRecommender().recommend(_note_with_scheduled_lorazepam_only(), client)

    user_prompt = client.set_user_prompt.call_args[0][0][0]
    system_prompt = client.set_system_prompt.call_args[0][0][0]
    assert "Transcript Excerpts" not in user_prompt
    assert "SAME DRUG, TWO ORDERS" not in system_prompt


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_transcript_only_medication_without_prn_language(mock_resolve: MagicMock) -> None:
    """A transcript with no as-needed phrasing adds nothing to the prompt."""
    mock_resolve.return_value = None
    client = _make_client({"medications": []})
    transcript = Transcript(
        items=[
            TranscriptItem(text="blood pressure looks good", speaker="doctor", start_offset_ms=0, end_offset_ms=5000)
        ]
    )

    MedicationRecommender().recommend(_note_with_scheduled_lorazepam_only(), client, transcript=transcript)

    assert "Transcript Excerpts" not in client.set_user_prompt.call_args[0][0][0]


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_recovered_medication_is_proposed_unselected(mock_resolve: MagicMock) -> None:
    """A medication recovered from the transcript is offered but not pre-selected.

    The provider never saw it in the generated note, so it must not be charted on their
    behalf — but it must be visible and one click away.
    """
    mock_resolve.return_value = None
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Lorazepam 0.5 mg",
                    "sig": "0.5 mg every four hours as needed for anxiety or agitation",
                    "keywords": "lorazepam, ativan",
                    "isPrn": True,
                    "fromTranscript": True,
                },
            ]
        }
    )

    proposals = MedicationRecommender().recommend(
        _note_with_scheduled_lorazepam_only(), client, transcript=_prn_transcript()
    )

    assert len(proposals) == 1
    assert proposals[0].from_transcript is True


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_note_derived_medication_stays_selected(mock_resolve: MagicMock) -> None:
    """A medication present in the note keeps the pre-existing selected-by-default behavior."""
    mock_resolve.return_value = None
    client = _make_client(
        {
            "medications": [
                {"medicationName": "Lisinopril 10 mg", "sig": "daily", "keywords": "lisinopril"},
            ]
        }
    )

    proposals = MedicationRecommender().recommend(_note_with_scheduled_lorazepam_only(), client)

    assert proposals[0].from_transcript is False


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_keeps_scheduled_and_prn_orders_for_the_same_drug(mock_resolve: MagicMock) -> None:
    """The lorazepam case: a scheduled order must not stand in for the as-needed one.

    Both entries survive as separate proposals, with only the recovered one unselected.
    """
    mock_resolve.return_value = None
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Lorazepam 0.5 mg",
                    "sig": "one tablet daily, one hour before showers on Mondays and Wednesdays",
                    "keywords": "lorazepam",
                },
                {
                    "medicationName": "Lorazepam 0.5 mg",
                    "sig": "0.5 mg every four hours as needed for anxiety or agitation",
                    "keywords": "lorazepam",
                    "isPrn": True,
                    "fromTranscript": True,
                },
            ]
        }
    )

    proposals = MedicationRecommender().recommend(
        _note_with_scheduled_lorazepam_only(), client, transcript=_prn_transcript()
    )

    assert len(proposals) == 2
    scheduled, prn = proposals
    assert scheduled.from_transcript is False
    assert prn.from_transcript is True
    assert "as needed" in prn.data["sig"]


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_runs_when_note_has_no_relevant_section_but_prns_were_dictated(
    mock_resolve: MagicMock,
) -> None:
    """Nabla dropping the medication section entirely must not skip extraction.

    Previously an empty section list returned [] before the LLM was ever called, so a note
    whose medications section Nabla omitted lost every dictated PRN silently.
    """
    mock_resolve.return_value = None
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Acetaminophen 650 mg",
                    "sig": "650 mg as needed for pain",
                    "keywords": "acetaminophen",
                    "isPrn": True,
                    "fromTranscript": True,
                },
            ]
        }
    )

    proposals = MedicationRecommender().recommend(_make_note([]), client, transcript=_prn_transcript())

    client.request.assert_called_once()
    assert len(proposals) == 1
    assert proposals[0].from_transcript is True


def test_recommend_skips_when_no_sections_and_no_prn_language() -> None:
    """With neither a relevant section nor as-needed phrasing, the LLM is never called."""
    client = _make_client({"medications": []})

    proposals = MedicationRecommender().recommend(_make_note([]), client)

    assert proposals == []
    client.request.assert_not_called()


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_ignores_from_transcript_when_no_excerpts_supplied(mock_resolve: MagicMock) -> None:
    """The model sets from_transcript even with no transcript; provenance must not trust it.

    Observed on real data: with no transcript passed at all, the LLM still returned
    fromTranscript=true, which would badge a medication as recovered on a note where no
    transcript was ever read. Provenance is a fact we establish, not one the model asserts.
    """
    mock_resolve.return_value = None
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Albuterol inhaler",
                    "sig": "approximately twice a week",
                    "keywords": "albuterol",
                    "fromTranscript": True,
                },
            ]
        }
    )

    proposals = MedicationRecommender().recommend(_note_with_scheduled_lorazepam_only(), client)

    assert proposals[0].from_transcript is False


@patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication")
def test_recommend_ignores_from_transcript_when_transcript_has_no_prn_language(
    mock_resolve: MagicMock,
) -> None:
    """A transcript with no as-needed phrasing supplies no excerpts, so nothing is recovered."""
    mock_resolve.return_value = None
    transcript = Transcript(
        items=[TranscriptItem(text="blood pressure is stable", speaker="doctor", start_offset_ms=0, end_offset_ms=4000)]
    )
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Lisinopril 10 mg",
                    "sig": "daily",
                    "keywords": "lisinopril",
                    "fromTranscript": True,
                },
            ]
        }
    )

    proposals = MedicationRecommender().recommend(_note_with_scheduled_lorazepam_only(), client, transcript=transcript)

    assert proposals[0].from_transcript is False


def test_recommend_clears_provenance_when_the_note_still_documents_the_prn() -> None:
    """Partial loss: Nabla drops the PRN from the med list but keeps it in the A&P.

    Measured on a real note — all six PRNs vanished from CURRENT_MEDICATIONS but survived in
    ASSESSMENT_AND_PLAN, and the model reported all six as transcript-recovered. The provider
    would have seen six "From transcript" pills on medications the note actually contained, and
    the audit counter overstated recoveries. Roughly half the affected notes in the ticket are
    partial, so this is the common case.
    """
    note = _make_note(
        [
            NoteSection(
                key="current_medications",
                title="Meds Discussed",
                text="- lorazepam, one tablet daily, one hour before showers on Mondays and Wednesdays",
            ),
            NoteSection(
                key="assessment_and_plan",
                title="Assessment & Plan",
                text=(
                    "Anxiety/agitation\n"
                    "- Add lorazepam 0.5 mg every four hours as needed for anxiety or agitation.\n"
                    "Insomnia\n"
                    "- Melatonin 3 mg as needed at bedtime."
                ),
            ),
        ]
    )
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Lorazepam 0.5 mg",
                    "sig": "every four hours as needed for anxiety",
                    "keywords": "lorazepam",
                    "isPrn": True,
                    "fromTranscript": True,
                },
                {
                    "medicationName": "Melatonin 3 mg",
                    "sig": "as needed at bedtime",
                    "keywords": "melatonin",
                    "isPrn": True,
                    "fromTranscript": True,
                },
            ]
        }
    )

    with patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication", return_value=None):
        proposals = MedicationRecommender().recommend(note, client, transcript=_prn_transcript())

    # both are in the A&P, so neither was recovered from anywhere
    assert [p.from_transcript for p in proposals] == [False, False]


def test_recommend_keeps_provenance_when_the_note_only_has_the_scheduled_order() -> None:
    """A genuine recovery must survive the guard.

    The note carries lorazepam only as a scheduled pre-shower dose, so the as-needed order really
    did come from the transcript and must stay flagged.
    """
    client = _make_client(
        {
            "medications": [
                {
                    "medicationName": "Lorazepam 0.5 mg",
                    "sig": "0.5 mg every four hours as needed for anxiety or agitation",
                    "keywords": "lorazepam",
                    "isPrn": True,
                    "fromTranscript": True,
                },
            ]
        }
    )

    with patch("hyperscribe.scribe.recommendations.medication_statement._resolve_medication", return_value=None):
        proposals = MedicationRecommender().recommend(
            _note_with_scheduled_lorazepam_only(), client, transcript=_prn_transcript()
        )

    assert proposals[0].from_transcript is True
