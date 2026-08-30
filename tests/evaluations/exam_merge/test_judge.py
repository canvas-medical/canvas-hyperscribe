from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from evaluations.exam_merge.case import ExamMergeCase
from evaluations.exam_merge.judge import (
    build_user_prompt,
    judge_case,
    judge_metrics,
    schema,
    verify_provenance,
)
from evaluations.structures.clause_verdict import (
    PROVENANCE_BLENDED,
    PROVENANCE_ENCOUNTER,
    PROVENANCE_TEMPLATE,
    PROVENANCE_UNKNOWN,
    ClauseVerdict,
)

SEED_CASE = Path("evaluations/cases/exam_merge/subsequent_visit_shoulder_dm")


@pytest.fixture(scope="module")
def seed() -> ExamMergeCase:
    return ExamMergeCase.from_directory(SEED_CASE)


def _verdict(**kwargs: Any) -> ClauseVerdict:
    base = {
        "row": "CARDIAC",
        "assertion": "Denies swelling in the legs",
        "provenance": PROVENANCE_UNKNOWN,
        "supported": False,
        "transcript_citation": "",
        "contradicted_by": "",
        "note": "",
    }
    base.update(kwargs)
    return ClauseVerdict(**base)  # type: ignore[arg-type]


# ── schema and loading ──


def test_schema_requires_every_field() -> None:
    required = schema()["items"]["required"]
    assert set(required) == {
        "row",
        "assertion",
        "provenance",
        "supported",
        "transcript_citation",
        "contradicted_by",
        "note",
    }
    assert schema()["items"]["additionalProperties"] is False


def test_load_from_json_defaults_to_unsupported() -> None:
    """A model omitting `supported` must not be read as "this is fine"."""
    loaded = ClauseVerdict.load_from_json([{"row": "A", "assertion": "x"}])
    assert loaded[0].supported is False
    assert loaded[0].provenance == PROVENANCE_UNKNOWN
    assert loaded[0].transcript_citation == ""


def test_load_from_json_coerces_null_strings() -> None:
    loaded = ClauseVerdict.load_from_json(
        [{"row": "A", "assertion": "x", "supported": True, "transcript_citation": None, "contradicted_by": None}]
    )
    assert loaded[0].transcript_citation == ""
    assert loaded[0].contradicted_by == ""


# ── prompt construction ──


def test_user_prompt_carries_both_sources_for_every_row(seed: ExamMergeCase) -> None:
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    prompt = "\n".join(build_user_prompt(data, seed.transcript_text(), seed.note_sections()))
    assert "### ROW: CARDIAC" in prompt
    assert "Denies chest pain, shortness of breath with exertion, or swelling in the legs." in prompt
    assert "No chest pain, palpitations, or shortness of breath" in prompt
    assert "(none, this row is encounter-only)" in prompt
    assert "## Encounter findings before the merge" in prompt


def test_user_prompt_includes_physical_exam_for_ros_contradiction_checks(seed: ExamMergeCase) -> None:
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    prompt = "\n".join(build_user_prompt(data, seed.transcript_text(), seed.note_sections()))
    assert "Trace bilateral ankle edema" in prompt


def test_user_prompt_excludes_the_section_under_audit(seed: ExamMergeCase) -> None:
    """A row must never be reported as contradicting itself."""
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    prompt = "\n".join(build_user_prompt(data, seed.transcript_text(), seed.note_sections()))
    assert "### review_of_systems" not in prompt
    assert "### PHYSICAL_EXAM" in prompt


def test_user_prompt_includes_the_transcript(seed: ExamMergeCase) -> None:
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    prompt = "\n".join(build_user_prompt(data, seed.transcript_text(), seed.note_sections()))
    assert "I do get winded on the stairs" in prompt


# ── provenance verification ──


def test_verify_provenance_corrects_a_template_only_clause(seed: ExamMergeCase) -> None:
    """ "swelling in the legs" is in CARDIAC's template text and not in its encounter text."""
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    checked = verify_provenance([_verdict(provenance=PROVENANCE_ENCOUNTER)], data)
    assert checked[0].provenance == PROVENANCE_TEMPLATE
    assert "provenance disputed" in checked[0].note


def test_verify_provenance_leaves_an_agreeing_claim_alone(seed: ExamMergeCase) -> None:
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    verdict = _verdict(provenance=PROVENANCE_TEMPLATE, note="fine")
    assert verify_provenance([verdict], data) == [verdict]


def test_verify_provenance_marks_a_shared_clause_blended(seed: ExamMergeCase) -> None:
    """ "chest pain" appears in both CARDIAC's template text and its encounter text."""
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    checked = verify_provenance([_verdict(assertion="Denies chest pain", provenance=PROVENANCE_TEMPLATE)], data)
    assert checked[0].provenance == PROVENANCE_BLENDED


def test_verify_provenance_keeps_claim_when_strings_are_silent(seed: ExamMergeCase) -> None:
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    verdict = _verdict(assertion="unrelated wording entirely", provenance=PROVENANCE_ENCOUNTER)
    assert verify_provenance([verdict], data) == [verdict]


def test_verify_provenance_ignores_assertions_with_no_long_words(seed: ExamMergeCase) -> None:
    data = next(d for d in seed.merge_kinds() if d.kind == "ros")
    verdict = _verdict(assertion="a b c", provenance=PROVENANCE_ENCOUNTER)
    assert verify_provenance([verdict], data) == [verdict]


# ── metrics ──


def test_judge_metrics_counts_unearned_and_contradicted() -> None:
    verdicts = [
        _verdict(assertion="a", supported=True, provenance=PROVENANCE_ENCOUNTER),
        _verdict(assertion="b", supported=False, provenance=PROVENANCE_TEMPLATE),
        _verdict(
            assertion="c", supported=False, provenance=PROVENANCE_BLENDED, contradicted_by="PHYSICAL_EXAM/EXTREMITIES"
        ),
        _verdict(assertion="d", supported=False, provenance=PROVENANCE_ENCOUNTER),
    ]
    metrics = judge_metrics(verdicts)
    assert metrics["assertions"] == 4
    assert metrics["unsupported"] == 3
    assert metrics["unearned_assertion_rate"] == 0.75
    assert metrics["template_sourced_unsupported"] == 2
    assert metrics["contradictions"] == 1


def test_judge_metrics_handles_no_assertions() -> None:
    metrics = judge_metrics([])
    assert metrics["assertions"] == 0
    assert metrics["unearned_assertion_rate"] is None


# ── orchestration ──


@patch("evaluations.case_builders.helper_synthetic_json.HelperSyntheticJson.generate_json")
def test_judge_case_runs_once_per_kind_and_verifies_provenance(mock_generate: MagicMock, seed: ExamMergeCase) -> None:
    mock_generate.return_value = [_verdict(provenance=PROVENANCE_ENCOUNTER)]

    verdicts, metrics = judge_case(seed)

    assert mock_generate.call_count == 2
    assert set(verdicts) == {"ros", "physical_exam"}
    assert set(metrics) == {"ros", "physical_exam"}
    # The ros call's claim was corrected against the real source strings.
    assert verdicts["ros"][0].provenance == PROVENANCE_TEMPLATE
    assert mock_generate.call_args_list[0][1]["returned_class"] is ClauseVerdict


@patch("evaluations.case_builders.helper_synthetic_json.HelperSyntheticJson.generate_json")
def test_judge_case_drops_non_verdict_results(mock_generate: MagicMock, seed: ExamMergeCase) -> None:
    mock_generate.return_value = ["not a verdict", _verdict()]
    verdicts, _ = judge_case(seed)
    assert len(verdicts["ros"]) == 1


def test_judge_model_is_not_the_model_that_produced_the_merge() -> None:
    """The judge exists to find defects in the merge. If it runs on the same model, shared
    blind spots go unreported, so this is pinned rather than left to convention."""
    from evaluations.exam_merge.judge import JUDGE_MODEL
    from hyperscribe.scribe.recommendations.reconciliation import _MODEL as MERGE_MODEL

    assert JUDGE_MODEL != MERGE_MODEL


@patch("evaluations.case_builders.helper_synthetic_json.HelperSyntheticJson.generate_json")
def test_judge_case_passes_the_judge_model_through(mock_generate: MagicMock, seed: ExamMergeCase) -> None:
    from evaluations.exam_merge.judge import JUDGE_MODEL

    mock_generate.return_value = [_verdict()]
    _, metrics = judge_case(seed)

    assert all(call[1]["model"] == JUDGE_MODEL for call in mock_generate.call_args_list)
    assert metrics["ros"]["judge_model"] == JUDGE_MODEL


@patch("evaluations.case_builders.helper_synthetic_json.HelperSyntheticJson.generate_json")
def test_judge_case_honors_an_explicit_model_override(mock_generate: MagicMock, seed: ExamMergeCase) -> None:
    mock_generate.return_value = [_verdict()]
    _, metrics = judge_case(seed, model="claude-sonnet-5")

    assert all(call[1]["model"] == "claude-sonnet-5" for call in mock_generate.call_args_list)
    assert metrics["physical_exam"]["judge_model"] == "claude-sonnet-5"
