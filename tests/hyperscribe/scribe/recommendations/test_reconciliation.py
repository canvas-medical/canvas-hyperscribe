import json
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.recommendations.reconciliation import (
    merge_sections,
    parse_exam_merge_kinds,
    reconcile_sections,
    refine_sections,
)


def _mock_llm_response(sections: list[dict[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(code=HTTPStatus.OK, response=json.dumps({"sections": sections}))


# ── parse_exam_merge_kinds ──


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, set()),
        ("", set()),
        ("   ", set()),
        (",,", set()),
        ("ros", {"ros"}),
        ("PHYSICAL_EXAM", {"physical_exam"}),
        (" ros , physical_exam ", {"ros", "physical_exam"}),
        ("ros,physical_exam,mental_status_exam", {"ros", "physical_exam", "mental_status_exam"}),
        ("ros,bogus", {"ros"}),
        ("bogus", set()),
        ("exam,reviewOfSystems", set()),
        ("ros,ros", {"ros"}),
    ],
)
def test_parse_exam_merge_kinds(raw: str | None, expected: set[str]) -> None:
    assert parse_exam_merge_kinds(raw) == expected


# ── merge_sections ──


def test_merge_exact_title_match_takes_encounter_text() -> None:
    template = [{"key": "general", "title": "General", "text": "Well-appearing."}]
    encounter = [{"key": "general", "title": "General", "text": "Ill-appearing, diaphoretic."}]

    assert merge_sections(template, encounter) == [
        {
            "key": "general",
            "title": "General",
            "text": "Ill-appearing, diaphoretic.",
            "updated": True,
            "template_text": "Well-appearing.",
        }
    ]


def test_merge_normalizes_title_before_matching() -> None:
    template = [{"key": "attention", "title": "Attention/Concentration", "text": "Sustained"}]
    encounter = [{"key": "x", "title": "  attention concentration  ", "text": "Distractible"}]

    merged = merge_sections(template, encounter)
    assert len(merged) == 1
    # The template's own label and key are what get displayed, not the encounter's.
    assert merged[0]["title"] == "Attention/Concentration"
    assert merged[0]["key"] == "attention"
    assert merged[0]["text"] == "Distractible"
    assert merged[0]["updated"] is True


def test_merge_keeps_template_text_for_uncovered_system() -> None:
    template = [{"key": "lungs", "title": "Lungs", "text": "Clear to auscultation bilaterally."}]

    assert merge_sections(template, []) == [
        {
            "key": "lungs",
            "title": "Lungs",
            "text": "Clear to auscultation bilaterally.",
            "updated": False,
            "template_text": "Clear to auscultation bilaterally.",
        }
    ]


def test_merge_empty_encounter_text_counts_as_not_covered() -> None:
    """The MSE case: Nabla emits all 11 labels, blank when a category was not addressed."""
    template = [{"key": "thought_content", "title": "Thought Content", "text": "No SI, no HI."}]
    encounter = [{"key": "thought_content", "title": "Thought Content", "text": "   "}]

    merged = merge_sections(template, encounter)
    assert merged[0]["text"] == "No SI, no HI."
    assert merged[0]["updated"] is False


def test_merge_preserves_template_ordering() -> None:
    template = [
        {"key": "general", "title": "General", "text": "a"},
        {"key": "heent", "title": "HEENT", "text": "b"},
        {"key": "cardio", "title": "Cardiovascular", "text": "c"},
    ]
    encounter = [{"key": "cardio", "title": "Cardiovascular", "text": "RRR"}]

    assert [s["title"] for s in merge_sections(template, encounter)] == ["General", "HEENT", "Cardiovascular"]


def test_merge_appends_encounter_only_systems_in_order() -> None:
    template = [{"key": "general", "title": "General", "text": "Well-appearing."}]
    encounter = [
        {"key": "skin", "title": "Skin", "text": "Rash on left forearm."},
        {"key": "neuro", "title": "Neuro", "text": "CN II-XII intact."},
    ]

    merged = merge_sections(template, encounter)
    assert [s["title"] for s in merged] == ["General", "Skin", "Neuro"]
    assert merged[1]["template_text"] is None
    assert merged[1]["updated"] is True
    assert merged[2]["template_text"] is None


def test_merge_drops_encounter_only_systems_with_no_text() -> None:
    merged = merge_sections([], [{"key": "skin", "title": "Skin", "text": "  "}])
    assert merged == []


def test_merge_empty_encounter_returns_whole_template_unchanged() -> None:
    template = [
        {"key": "general", "title": "General", "text": "a"},
        {"key": "heent", "title": "HEENT", "text": "b"},
    ]

    merged = merge_sections(template, [])
    assert [s["text"] for s in merged] == ["a", "b"]
    assert all(s["updated"] is False for s in merged)


def test_merge_first_encounter_row_wins_on_duplicate_titles() -> None:
    template = [{"key": "general", "title": "General", "text": "template"}]
    encounter = [
        {"key": "general", "title": "General", "text": "first"},
        {"key": "general2", "title": "General", "text": "second"},
    ]

    merged = merge_sections(template, encounter)
    assert len(merged) == 1
    assert merged[0]["text"] == "first"


def test_merge_with_no_template_returns_encounter_only() -> None:
    encounter = [{"key": "general", "title": "General", "text": "Well-appearing."}]

    merged = merge_sections([], encounter)
    assert len(merged) == 1
    assert merged[0]["template_text"] is None
    assert merged[0]["updated"] is True


# ── refine_sections ──


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_llm_sections_with_template_text_attached(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = _mock_llm_response(
        [
            {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever.", "updated": False},
            {"key": "eyes", "title": "EYES", "text": "Blurred vision noted.", "updated": True},
        ]
    )
    template = [
        {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever."},
        {"key": "eyes", "title": "EYES", "text": "Denies visual changes."},
    ]
    encounter = [{"key": "eyes", "title": "EYES", "text": "Blurred vision noted."}]

    result = refine_sections(merge_sections(template, encounter), template, encounter, "k", "Review of Systems")

    assert result is not None
    assert result[0]["template_text"] == "Denies fever."
    assert result[1]["updated"] is True
    assert result[1]["template_text"] == "Denies visual changes."
    mock_client.set_system_prompt.assert_called_once()
    mock_client.set_user_prompt.assert_called_once()
    mock_client.set_schema.assert_called_once()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_new_system_has_no_template_text(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = _mock_llm_response(
        [{"key": "respiratory", "title": "RESPIRATORY", "text": "Mild wheezing.", "updated": True}]
    )

    result = refine_sections([{"key": "x", "title": "X", "text": "y"}], [], [], "k", "Review of Systems")

    assert result is not None
    assert result[0]["template_text"] is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_none_without_api_key(mock_llm_cls: MagicMock) -> None:
    assert refine_sections([{"key": "a", "title": "A", "text": "b"}], [], [], "", "Physical Exam") is None
    mock_llm_cls.assert_not_called()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_none_on_empty_draft(mock_llm_cls: MagicMock) -> None:
    assert refine_sections([], [], [], "k", "Physical Exam") is None
    mock_llm_cls.assert_not_called()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_none_on_transport_error(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.side_effect = RuntimeError("connection reset")

    assert refine_sections([{"key": "a", "title": "A", "text": "b"}], [], [], "k", "Physical Exam") is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_none_on_non_200(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = SimpleNamespace(code=HTTPStatus.TOO_MANY_REQUESTS, response="rate limited")

    assert refine_sections([{"key": "a", "title": "A", "text": "b"}], [], [], "k", "Physical Exam") is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_none_on_unparseable_response(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = SimpleNamespace(code=HTTPStatus.OK, response="not json")

    assert refine_sections([{"key": "a", "title": "A", "text": "b"}], [], [], "k", "Physical Exam") is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_refine_returns_none_when_llm_returns_no_sections(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = _mock_llm_response([])

    assert refine_sections([{"key": "a", "title": "A", "text": "b"}], [], [], "k", "Physical Exam") is None


# ── reconcile_sections ──


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_returns_refined_when_llm_succeeds(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = _mock_llm_response(
        [{"key": "cardio", "title": "Cardiovascular", "text": "RRR, no murmur, no edema.", "updated": True}]
    )
    template = [{"key": "cardio", "title": "Cardiovascular", "text": "RRR, no edema."}]
    encounter = [{"key": "cv", "title": "CV", "text": "RRR, no murmur."}]

    sections, refined = reconcile_sections(template, encounter, "k", "Physical Exam")

    assert refined is True
    assert sections[0]["text"] == "RRR, no murmur, no edema."


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_falls_back_to_deterministic_merge_on_llm_failure(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.side_effect = RuntimeError("anthropic down")
    template = [
        {"key": "general", "title": "General", "text": "Well-appearing."},
        {"key": "lungs", "title": "Lungs", "text": "Clear to auscultation."},
    ]
    encounter = [{"key": "general", "title": "General", "text": "Ill-appearing."}]

    sections, refined = reconcile_sections(template, encounter, "k", "Physical Exam")

    assert refined is False
    # The provider still gets full system coverage; only the blending is lost.
    assert [s["text"] for s in sections] == ["Ill-appearing.", "Clear to auscultation."]
    assert [s["updated"] for s in sections] == [True, False]


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_skips_llm_entirely_when_refine_disallowed(mock_llm_cls: MagicMock) -> None:
    template = [{"key": "general", "title": "General", "text": "Well-appearing."}]

    sections, refined = reconcile_sections(template, [], "k", "Physical Exam", allow_refine=False)

    assert refined is False
    assert sections[0]["text"] == "Well-appearing."
    mock_llm_cls.assert_not_called()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_without_api_key_returns_deterministic_merge(mock_llm_cls: MagicMock) -> None:
    template = [{"key": "general", "title": "General", "text": "Well-appearing."}]

    sections, refined = reconcile_sections(template, [], "", "Physical Exam")

    assert refined is False
    assert len(sections) == 1
    mock_llm_cls.assert_not_called()
