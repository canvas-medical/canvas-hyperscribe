import json
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.recommendations.reconciliation import (
    buried_systems,
    content_words,
    normalize_title,
    overlap_ratio,
    parse_exam_merge_kinds,
    coverage_gaps,
    reconcile_sections,
    validate_merge,
)

TEMPLATE = [
    {"key": "general", "title": "General", "text": "Well-appearing."},
    {"key": "lungs", "title": "Lungs", "text": "Clear to auscultation."},
]
ENCOUNTER = [{"key": "gen", "title": "Gen", "text": "Ill-appearing, diaphoretic."}]


def _section(title: str, text: str, clauses: list[dict[str, str]] | None = None, **extra: Any) -> dict[str, Any]:
    section: dict[str, Any] = {
        "key": title.lower(),
        "title": title,
        "text": text,
        "updated": True,
        "clauses": clauses if clauses is not None else [{"text": text, "provenance": "encounter"}],
    }
    section.update(extra)
    return section


def _llm_response(sections: list[dict[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(code=HTTPStatus.OK, response=json.dumps({"sections": sections}))


# ── the secret gate ──


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, set()),
        ("", set()),
        ("ros", {"ros"}),
        ("PHYSICAL_EXAM", {"physical_exam"}),
        (" ros , physical_exam ", {"ros", "physical_exam"}),
        ("ros,bogus", {"ros"}),
        ("exam,reviewOfSystems", set()),
    ],
)
def test_parse_exam_merge_kinds(raw: str | None, expected: set[str]) -> None:
    assert parse_exam_merge_kinds(raw) == expected


# ── text helpers, shared with the eval harness ──


def test_normalize_title_flattens_slashes() -> None:
    """The bug this fixes: the scaffold parser emits the key ``si/hi`` while the model
    returns ``si_hi``, so a key-based lookup lost template_text for every slash-named
    system (SI/HI, DELUSIONS/PARANOIA, Behavior/Rapport, Attention/Concentration)."""
    assert normalize_title("SI/HI") == normalize_title("si_hi") == "si hi"
    assert normalize_title("DELUSIONS/PARANOIA") == normalize_title("delusions_paranoia")
    assert normalize_title("Attention/Concentration") == normalize_title("attention_concentration")
    assert normalize_title("  HEENT  ") == "heent"
    assert normalize_title("") == ""


def test_content_words_drops_stopwords_and_short_tokens() -> None:
    assert content_words("Denies fever and chills") == {"fever", "chills"}
    assert content_words("") == set()


def test_overlap_ratio_is_inflection_tolerant() -> None:
    assert overlap_ratio("No rashes", "Denies rash.") == 1.0
    assert overlap_ratio("splenomegaly palpated", "Denies fever.") == 0.0
    assert overlap_ratio("", "anything") == 1.0


# ── validate_merge ──


def test_validate_accepts_a_good_merge() -> None:
    sections = [
        _section("General", "Ill-appearing, diaphoretic.", template_text="Well-appearing."),
        _section("Lungs", "Clear to auscultation.", template_text="Clear to auscultation.", updated=False),
    ]
    assert validate_merge(sections, TEMPLATE, ENCOUNTER) == []


def test_validate_rejects_an_empty_merge() -> None:
    assert validate_merge([], TEMPLATE, ENCOUNTER) == ["the merge returned no sections"]


def test_validate_rejects_a_placeholder() -> None:
    """The floor used to ship 'Alert and oriented to ***' straight into the chart."""
    sections = [_section("General", "Alert and oriented to ***. Ill-appearing, diaphoretic.")]
    errors = validate_merge(sections, TEMPLATE, ENCOUNTER)
    assert any("placeholder" in e for e in errors)


@pytest.mark.parametrize("blank", ["___", "[fill in]", "<name>"])
def test_validate_rejects_every_placeholder_form(blank: str) -> None:
    sections = [_section("General", f"Ill-appearing, diaphoretic. {blank}")]
    assert any("placeholder" in e for e in validate_merge(sections, TEMPLATE, ENCOUNTER))


def test_validate_rejects_duplicate_rows() -> None:
    sections = [
        _section("General", "Ill-appearing, diaphoretic."),
        _section("general", "something else"),
    ]
    assert any("duplicate" in e for e in validate_merge(sections, TEMPLATE, ENCOUNTER))


def test_validate_rejects_a_row_with_no_title() -> None:
    sections = [_section("General", "Ill-appearing, diaphoretic."), _section("", "orphan")]
    assert any("no title" in e for e in validate_merge(sections, TEMPLATE, ENCOUNTER))


def test_validate_rejects_reordered_template_systems() -> None:
    sections = [
        _section("Lungs", "Clear to auscultation."),
        _section("General", "Ill-appearing, diaphoretic."),
    ]
    assert any("order" in e for e in validate_merge(sections, TEMPLATE, ENCOUNTER))


def test_validate_does_not_reject_a_dropped_encounter_finding() -> None:
    """Coverage is advisory. Lexical matching cannot tell a genuine drop from a synonym,
    and rejecting on a false positive would cost the note its whole merge."""
    sections = [_section("General", "Well-appearing."), _section("Lungs", "Clear to auscultation.")]
    assert validate_merge(sections, TEMPLATE, ENCOUNTER) == []


def test_validate_allows_a_consolidated_encounter_finding() -> None:
    """The merge may fold an encounter row into a template row under a different name."""
    sections = [
        _section("General", "Ill-appearing, diaphoretic."),
        _section("Lungs", "Clear to auscultation."),
    ]
    assert validate_merge(sections, TEMPLATE, ENCOUNTER) == []


# ── coverage_gaps, advisory ──


def test_coverage_gaps_reports_a_dropped_finding() -> None:
    sections = [_section("General", "Well-appearing."), _section("Lungs", "Clear to auscultation.")]
    assert coverage_gaps(sections, ENCOUNTER) == ["Gen"]


def test_coverage_gaps_is_quiet_when_the_finding_was_consolidated() -> None:
    sections = [_section("General", "Ill-appearing, diaphoretic.")]
    assert coverage_gaps(sections, ENCOUNTER) == []


def test_coverage_gaps_uses_the_title_for_bare_negations() -> None:
    """Measured case: "Homicidal ideation: none" folded into an SI/HI row read as absent
    when only the text was compared, because "none" carries no distinguishing words."""
    sections = [
        _section(
            "SI/HI",
            "Reports passive suicidal ideation without plan. Denies homicidal ideation with plan.",
        )
    ]
    encounter = [{"key": "hi", "title": "Homicidal ideation", "text": "none"}]
    assert coverage_gaps(sections, encounter) == []


# ── reconcile_sections ──


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_returns_the_merge_on_success(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = _llm_response(
        [
            _section("General", "Ill-appearing, diaphoretic."),
            _section("Lungs", "Clear to auscultation.", updated=False),
        ]
    )

    sections, merged = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert merged is True
    assert [s["title"] for s in sections] == ["General", "Lungs"]
    assert client.request.call_count == 1


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_attaches_template_text_by_title_not_key(mock_llm: MagicMock) -> None:
    """The slash-key fix, end to end."""
    client = MagicMock()
    mock_llm.return_value = client
    template = [{"key": "si/hi", "title": "SI/HI", "text": "Denies suicidal ideation with plan."}]
    client.request.return_value = _llm_response(
        [_section("SI/HI", "Reports passive suicidal ideation without plan.", **{"key": "si_hi"})]
    )

    sections, merged = reconcile_sections(template, [], "k", "Review of Systems")

    assert merged is True
    assert sections[0]["template_text"] == "Denies suicidal ideation with plan."
    assert sections[0]["updated"] is True


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_derives_updated_rather_than_trusting_the_model(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    # Model says updated=True while returning the template text verbatim.
    client.request.return_value = _llm_response(
        [
            _section("General", "Well-appearing.", updated=True),
            _section("Lungs", "Clear to auscultation.", updated=True),
        ]
    )

    sections, _ = reconcile_sections(TEMPLATE, [], "k", "Physical Exam")

    assert [s["updated"] for s in sections] == [False, False]


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_carries_clauses_through(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    clauses = [
        {"text": "Ill-appearing", "provenance": "encounter"},
        {"text": "well nourished", "provenance": "template"},
    ]
    client.request.return_value = _llm_response(
        [
            _section("General", "Ill-appearing, well nourished.", clauses=clauses),
            _section("Lungs", "Clear to auscultation."),
        ]
    )

    sections, _ = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert sections[0]["clauses"] == clauses


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_retries_once_then_succeeds(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.side_effect = [
        _llm_response([_section("General", "Alert and oriented to ***.")]),  # placeholder, rejected
        _llm_response(
            [_section("General", "Ill-appearing, diaphoretic."), _section("Lungs", "Clear to auscultation.")]
        ),
    ]

    sections, merged = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert merged is True
    assert client.request.call_count == 2


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_feeds_the_validation_errors_into_the_retry(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.side_effect = [
        _llm_response([_section("General", "Alert and oriented to ***.")]),
        _llm_response(
            [_section("General", "Ill-appearing, diaphoretic."), _section("Lungs", "Clear to auscultation.")]
        ),
    ]

    reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    retry_prompt = "\n".join(client.set_user_prompt.call_args_list[1][0][0])
    assert "previous attempt was rejected" in retry_prompt
    assert "placeholder" in retry_prompt


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_gives_up_after_two_failures(mock_llm: MagicMock) -> None:
    """Empty result tells the caller to leave generation's own findings alone, which is
    the behavior that shipped before the merge existed."""
    client = MagicMock()
    mock_llm.return_value = client
    client.request.side_effect = [
        _llm_response([_section("General", "Alert and oriented to ***.")]),
        _llm_response([_section("General", "Still ___ broken.")]),
    ]

    sections, merged = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert (sections, merged) == ([], False)
    assert client.request.call_count == 2


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_gives_up_when_the_call_keeps_raising(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.side_effect = RuntimeError("anthropic down")

    assert reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam") == ([], False)
    assert client.request.call_count == 2


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_handles_a_non_200(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = SimpleNamespace(code=HTTPStatus.TOO_MANY_REQUESTS, response="rate limited")

    assert reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam") == ([], False)


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_handles_an_unparseable_response(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = SimpleNamespace(code=HTTPStatus.OK, response="not json")

    assert reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam") == ([], False)


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_skips_the_call_without_an_api_key(mock_llm: MagicMock) -> None:
    assert reconcile_sections(TEMPLATE, ENCOUNTER, "", "Physical Exam") == ([], False)
    mock_llm.assert_not_called()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_skips_the_call_when_the_circuit_is_open(mock_llm: MagicMock) -> None:
    assert reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam", allow_llm=False) == ([], False)
    mock_llm.assert_not_called()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_skips_the_call_without_a_template(mock_llm: MagicMock) -> None:
    assert reconcile_sections([], ENCOUNTER, "k", "Physical Exam") == ([], False)
    mock_llm.assert_not_called()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_passes_the_other_note_sections_for_the_contradiction_rule(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = _llm_response(
        [_section("General", "Ill-appearing, diaphoretic."), _section("Lungs", "Clear to auscultation.")]
    )

    reconcile_sections(
        TEMPLATE,
        ENCOUNTER,
        "k",
        "Review of Systems",
        note_sections=[{"key": "PHYSICAL_EXAM", "text": "Extremities: Trace bilateral ankle edema"}],
    )

    prompt = "\n".join(client.set_user_prompt.call_args_list[0][0][0])
    assert "Trace bilateral ankle edema" in prompt
    assert "for rule 5" in prompt


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_system_prompt_carries_the_never_widen_and_never_contradict_rules(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = _llm_response(
        [_section("General", "Ill-appearing, diaphoretic."), _section("Lungs", "Clear to auscultation.")]
    )

    reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    prompt = "\n".join(client.set_system_prompt.call_args[0][0])
    assert "NEVER WIDEN A DENIAL" in prompt
    assert "NEVER CONTRADICT THE REST OF THE NOTE" in prompt
    assert "No rashes" in prompt


# ── doubly-encoded tool output ──


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_recovers_a_doubly_encoded_payload(mock_llm: MagicMock) -> None:
    """Measured: claude-sonnet-5 returned {"sections": "<the whole JSON as a string>"} on
    4 of 4 merge calls, with perfectly good content inside. Without this the model is
    unusable here for reasons unrelated to its clinical reasoning."""
    client = MagicMock()
    mock_llm.return_value = client
    inner = {
        "sections": [
            _section("General", "Ill-appearing, diaphoretic."),
            _section("Lungs", "Clear to auscultation."),
        ]
    }
    client.request.return_value = SimpleNamespace(
        code=HTTPStatus.OK, response=json.dumps({"sections": json.dumps(inner)})
    )

    sections, merged = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert merged is True
    assert [s["title"] for s in sections] == ["General", "Lungs"]


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_recovers_a_bare_encoded_list(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    rows = [_section("General", "Ill-appearing, diaphoretic."), _section("Lungs", "Clear to auscultation.")]
    client.request.return_value = SimpleNamespace(
        code=HTTPStatus.OK, response=json.dumps({"sections": json.dumps(rows)})
    )

    sections, merged = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert merged is True
    assert len(sections) == 2


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_leaves_a_normal_payload_alone(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = _llm_response(
        [_section("General", "Ill-appearing, diaphoretic."), _section("Lungs", "Clear to auscultation.")]
    )

    sections, merged = reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam")

    assert merged is True
    assert len(sections) == 2


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_gives_up_on_an_unrecoverable_string(mock_llm: MagicMock) -> None:
    client = MagicMock()
    mock_llm.return_value = client
    client.request.return_value = SimpleNamespace(
        code=HTTPStatus.OK, response=json.dumps({"sections": "not json at all"})
    )

    assert reconcile_sections(TEMPLATE, ENCOUNTER, "k", "Physical Exam") == ([], False)


def test_merge_model_needs_no_client_workaround() -> None:
    """The merge must stay on a model the shipped SDK client can actually talk to.

    canvas_sdk's LlmAnthropic always sends the deprecated `temperature` and reads the
    response as content[0]["input"], which is a thinking block on 4.7+ models. Anything
    from that generation onward needs a client fix first, so pinning the merge to one
    means the plugin silently stops merging.
    """
    from hyperscribe.scribe.recommendations.reconciliation import _MODEL

    needs_client_fix = {"claude-opus-5", "claude-sonnet-5", "claude-opus-4-8", "claude-opus-4-7"}
    assert _MODEL not in needs_client_fix, (
        f"{_MODEL} requires dropping `temperature` and reading the first text block; "
        "fix canvas_sdk's LlmAnthropic before pinning the merge to it"
    )


# ── the catch-all dumping ground (buried_systems) ──


def test_buried_systems_flags_encounter_systems_folded_into_a_catch_all() -> None:
    """A template ending in "OTHER: None reported." reads as an invitation, and the model
    funnelled four encounter-only systems into it as inline labels. The content survived,
    so coverage saw nothing; the shape was legal, so ordering and duplicates saw nothing."""
    sections = [
        {"title": "SKIN", "text": "No rashes. Callus on right foot."},
        {
            "title": "OTHER",
            "text": (
                "Neurologic: No headaches, no dizziness. Psychiatric: Flat affect. "
                "Endocrine: Elevated blood sugars. Genitourinary: No urinary issues."
            ),
        },
    ]
    encounter = [
        {"title": "Skin", "text": "No rashes"},
        {"title": "Neurologic", "text": "No headaches"},
        {"title": "Psychiatric", "text": "Flat affect"},
        {"title": "Endocrine", "text": "High sugars"},
        {"title": "Genitourinary", "text": "No urinary issues"},
    ]
    buried = buried_systems(sections, encounter)
    assert [name for name, _ in buried] == ["neurologic", "psychiatric", "endocrine", "genitourinary"]
    assert {row for _, row in buried} == {"OTHER"}


def test_buried_systems_quiet_when_each_system_has_its_own_row() -> None:
    sections = [
        {"title": "SKIN", "text": "No rashes."},
        {"title": "NEUROLOGIC", "text": "No headaches, no dizziness."},
        {"title": "OTHER", "text": "None reported."},
    ]
    encounter = [{"title": "Skin", "text": "x"}, {"title": "Neurologic", "text": "y"}]
    assert buried_systems(sections, encounter) == []


def test_buried_systems_ignores_a_label_for_a_system_that_does_have_a_row() -> None:
    """Consolidation is legal, so a template row may legitimately mention a system it
    absorbed. Only a system with nowhere else to live counts as buried."""
    sections = [{"title": "NEUROLOGIC", "text": "Neurologic: no headaches."}]
    assert buried_systems(sections, [{"title": "Neurologic", "text": "x"}]) == []


def test_validate_merge_rejects_a_catch_all_dumping_ground() -> None:
    sections = [
        {"title": "SKIN", "text": "No rashes."},
        {"title": "OTHER", "text": "Neurologic: No headaches. Psychiatric: Flat affect."},
    ]
    template = [{"title": "SKIN", "text": "x"}, {"title": "OTHER", "text": "None reported."}]
    encounter = [{"title": "Neurologic", "text": "a"}, {"title": "Psychiatric", "text": "b"}]
    errors = validate_merge(sections, template, encounter)
    assert len(errors) == 2
    assert all("instead of getting its own row" in e for e in errors)


def test_validate_merge_rejects_packed_rows_even_for_unnamed_systems() -> None:
    """Backstop for the case where the model relabels while packing, so the inline label
    no longer matches an encounter title. Known-good output carries zero inline labels."""
    sections = [{"title": "OTHER", "text": "Neuro: no headaches. Psych: flat affect."}]
    errors = validate_merge(sections, [{"title": "OTHER", "text": "None reported."}], [])
    assert errors == ["row 'OTHER' packs 2 systems into one row as inline labels; emit one row per system"]


def test_validate_merge_allows_a_single_inline_label() -> None:
    """One colon in a row is ordinary prose, not a packed row."""
    sections = [{"title": "PSYCH", "text": "Mood: depressed with congruent affect."}]
    assert validate_merge(sections, [{"title": "PSYCH", "text": "x"}], []) == []


def test_validate_merge_does_not_double_report_a_buried_row() -> None:
    """A row caught by the precise check is not also reported by the packed backstop."""
    sections = [{"title": "OTHER", "text": "Neurologic: none. Psychiatric: none."}]
    encounter = [{"title": "Neurologic", "text": "a"}, {"title": "Psychiatric", "text": "b"}]
    errors = validate_merge(sections, [{"title": "OTHER", "text": "None reported."}], encounter)
    assert all("packs" not in e for e in errors)
