import json
from pathlib import Path
from typing import Any

import pytest

from evaluations.exam_merge.case import ExamMergeCase
from evaluations.exam_merge.invariants import (
    SEVERITY_FAIL,
    SEVERITY_INFO,
    SEVERITY_WARN,
    check_case,
    check_encounter_coverage,
    check_provenance_flags,
    check_template_ordering,
    normalize_title,
)

SEED_CASE = Path("evaluations/cases/exam_merge/subsequent_visit_shoulder_dm")

TEMPLATES = {
    "templates": [
        {
            "name": "T",
            "ros_template": "ALPHA: Denies alpha things.\nBETA: Denies beta things.",
            "pe_template": None,
        }
    ]
}


def _case(sections: list[dict[str, Any]], encounter: list[dict[str, Any]], **data_extra: Any) -> ExamMergeCase:
    data: dict[str, Any] = {
        "sections": sections,
        "encounter_sections": encounter,
        "reconciled_sections": [dict(s) for s in sections],
        "template_removed": False,
    }
    data.update(data_extra)
    return ExamMergeCase(
        name="synthetic",
        transcript={"items": []},
        visit_templates=TEMPLATES,
        summary={
            "selected_template_name": "T",
            "commands": [{"command_type": "ros", "section_key": "_ros", "data": data}],
            "note_data": {"sections": []},
        },
    )


def _kind(case: ExamMergeCase) -> Any:
    return next(d for d in case.merge_kinds() if d.kind == "ros")


# ── the seed case pins the known-good numbers ──


@pytest.fixture(scope="module")
def seed() -> ExamMergeCase:
    return ExamMergeCase.from_directory(SEED_CASE)


def test_seed_case_reproduces_known_counts(seed: ExamMergeCase) -> None:
    _, metrics = check_case(seed)
    by_kind = {k["kind"]: k for k in metrics["kinds"]}

    assert metrics["template_name"] == "Subsequent Visit"
    assert by_kind["ros"]["template_rows"] == 7
    assert by_kind["ros"]["encounter_rows"] == 9
    assert by_kind["ros"]["final_rows"] == 10
    assert by_kind["physical_exam"]["template_rows"] == 6
    assert by_kind["physical_exam"]["encounter_rows"] == 10
    assert by_kind["physical_exam"]["final_rows"] == 10


def test_seed_case_predates_clause_provenance(seed: ExamMergeCase) -> None:
    """The seed artifact was captured before clauses existed, so M8 says so once per
    section rather than flooding one warning per row."""
    findings, metrics = check_case(seed)
    m8 = [f for f in findings if f.check_id == "M8"]
    assert {f.severity for f in m8} == {SEVERITY_INFO}
    assert len(m8) == 2
    by_kind = {k["kind"]: k for k in metrics["kinds"]}
    assert by_kind["ros"]["total_clauses"] == 0
    assert by_kind["ros"]["template_clause_share"] is None


def test_seed_case_passes_the_runtime_validator(seed: ExamMergeCase) -> None:
    """M5 re-runs validate_merge over the artifact. A shipped merge should pass it."""
    findings, _ = check_case(seed)
    assert [f for f in findings if f.check_id == "M5"] == []


def test_seed_case_has_no_rows_missing_template_text(seed: ExamMergeCase) -> None:
    """The slash-key bug shows up here: a row whose title is in the template but whose
    template_text is null. Subsequent Visit has no slash-named systems, so it is clean."""
    _, metrics = check_case(seed)
    assert all(k["rows_missing_template_text"] == 0 for k in metrics["kinds"])


def test_seed_case_warns_on_consolidated_lymphatic_row(seed: ExamMergeCase) -> None:
    findings, _ = check_case(seed)
    rows = {f.row for f in findings if f.check_id == "M4" and f.severity == SEVERITY_WARN}
    assert "Lymphatic" in rows


def test_seed_case_has_no_provenance_or_ordering_failures(seed: ExamMergeCase) -> None:
    findings, _ = check_case(seed)
    assert [f for f in findings if f.check_id in {"M1", "M2", "M3", "M7"}] == []


def test_seed_case_template_sourced_row_count(seed: ExamMergeCase) -> None:
    _, metrics = check_case(seed)
    by_kind = {k["kind"]: k for k in metrics["kinds"]}
    # SKIN and OTHER carry template text verbatim; the physical exam carries none.
    assert by_kind["ros"]["template_sourced_rows"] == 2
    assert by_kind["physical_exam"]["template_sourced_rows"] == 0


# ── negative direction: the checks must actually fail when the data is wrong ──


def test_m1_fails_when_unchanged_row_text_differs_from_template() -> None:
    case = _case(
        [
            {
                "key": "alpha",
                "title": "ALPHA",
                "text": "something else",
                "updated": False,
                "template_text": "Denies alpha things.",
            }
        ],
        [],
    )
    findings = check_provenance_flags(_kind(case))
    assert [(f.check_id, f.severity) for f in findings] == [("M1", SEVERITY_FAIL)]


def test_m2_fails_when_updated_row_matches_template_verbatim() -> None:
    case = _case(
        [
            {
                "key": "alpha",
                "title": "ALPHA",
                "text": "Denies alpha things.",
                "updated": True,
                "template_text": "Denies alpha things.",
            }
        ],
        [],
    )
    findings = check_provenance_flags(_kind(case))
    assert [(f.check_id, f.severity) for f in findings] == [("M2", SEVERITY_FAIL)]


def test_m2_fails_when_row_without_template_text_claims_not_updated() -> None:
    case = _case(
        [{"key": "gamma", "title": "GAMMA", "text": "encounter only", "updated": False, "template_text": None}],
        [],
    )
    findings = check_provenance_flags(_kind(case))
    assert [(f.check_id, f.severity) for f in findings] == [("M2", SEVERITY_FAIL)]


def test_m3_warns_when_template_rows_are_reordered() -> None:
    case = _case(
        [
            {"key": "beta", "title": "BETA", "text": "b", "updated": True, "template_text": "Denies beta things."},
            {"key": "alpha", "title": "ALPHA", "text": "a", "updated": True, "template_text": "Denies alpha things."},
        ],
        [],
    )
    findings = check_template_ordering(_kind(case))
    assert [(f.check_id, f.severity) for f in findings] == [("M3", SEVERITY_WARN)]


def test_m4_fails_when_an_encounter_finding_disappears() -> None:
    case = _case(
        [
            {
                "key": "alpha",
                "title": "ALPHA",
                "text": "Denies alpha things.",
                "updated": False,
                "template_text": "Denies alpha things.",
            }
        ],
        [{"key": "zeta", "title": "ZETA", "text": "splenomegaly palpated"}],
    )
    findings = check_encounter_coverage(_kind(case))
    assert [(f.check_id, f.severity, f.row) for f in findings] == [("M4", SEVERITY_FAIL, "ZETA")]


def test_m4_tolerates_inflection_differences() -> None:
    """ "No rashes" surviving as "rash" is content preserved, not content lost."""
    case = _case(
        [
            {
                "key": "alpha",
                "title": "ALPHA",
                "text": "Denies rash.",
                "updated": True,
                "template_text": "Denies alpha things.",
            }
        ],
        [{"key": "alpha", "title": "ALPHA", "text": "No rashes"}],
    )
    assert check_encounter_coverage(_kind(case)) == []


def test_m7_fails_when_reference_copies_are_missing() -> None:
    case = ExamMergeCase(
        name="synthetic",
        transcript={"items": []},
        visit_templates=TEMPLATES,
        summary={
            "selected_template_name": "T",
            "commands": [{"command_type": "ros", "data": {"sections": []}}],
            "note_data": {"sections": []},
        },
    )
    findings, _ = check_case(case)
    assert ("M7", SEVERITY_FAIL) in [(f.check_id, f.severity) for f in findings]


def test_m7_fails_when_reconciled_sections_alias_sections() -> None:
    shared: list[dict[str, Any]] = [
        {"key": "alpha", "title": "ALPHA", "text": "a", "updated": True, "template_text": "Denies alpha things."}
    ]
    case = ExamMergeCase(
        name="synthetic",
        transcript={"items": []},
        visit_templates=TEMPLATES,
        summary={
            "selected_template_name": "T",
            "commands": [
                {
                    "command_type": "ros",
                    "data": {"sections": shared, "encounter_sections": [], "reconciled_sections": shared},
                }
            ],
            "note_data": {"sections": []},
        },
    )
    findings, _ = check_case(case)
    assert any(f.check_id == "M7" and "same object" in f.message for f in findings)


# ── no-op cases ──


def test_case_with_no_scaffold_reports_info_not_failure() -> None:
    case = ExamMergeCase(
        name="synthetic",
        transcript={"items": []},
        visit_templates={"templates": [{"name": "T", "ros_template": None, "pe_template": None}]},
        summary={"selected_template_name": "T", "commands": [], "note_data": {"sections": []}},
    )
    findings, metrics = check_case(case)
    assert metrics["kinds"] == []
    assert [(f.check_id, f.severity) for f in findings] == [("M0", SEVERITY_INFO)]


def test_unknown_template_name_yields_no_scaffold() -> None:
    case = ExamMergeCase(
        name="synthetic",
        transcript={"items": []},
        visit_templates=TEMPLATES,
        summary={"selected_template_name": "Does Not Exist", "commands": [], "note_data": {"sections": []}},
    )
    assert case.template_sections("ros") == []


def test_normalize_title_matches_merge_sections_behavior() -> None:
    assert normalize_title("Attention/Concentration") == "attention concentration"
    assert normalize_title("  HEENT  ") == "heent"
    assert normalize_title("") == ""


def test_seed_case_report_json_is_serializable(seed: ExamMergeCase, tmp_path: Path) -> None:
    findings, metrics = check_case(seed)
    payload = {"metrics": metrics, "findings": [f.to_json() for f in findings]}
    (tmp_path / "r.json").write_text(json.dumps(payload))
    assert json.loads((tmp_path / "r.json").read_text())["metrics"]["template_name"] == "Subsequent Visit"
