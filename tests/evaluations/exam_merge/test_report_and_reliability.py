import csv
import json
from pathlib import Path
from typing import Any

import pytest

from evaluations.exam_merge import reliability, report
from evaluations.exam_merge.case import ExamMergeCase
from evaluations.exam_merge.invariants import SEVERITY_FAIL, SEVERITY_WARN, Finding, check_case
from evaluations.structures.clause_verdict import PROVENANCE_TEMPLATE, ClauseVerdict

SEED_CASE = Path("evaluations/cases/exam_merge/subsequent_visit_shoulder_dm")


@pytest.fixture(scope="module")
def seed() -> ExamMergeCase:
    return ExamMergeCase.from_directory(SEED_CASE)


# ── report ──


def test_findings_rows_put_failures_first() -> None:
    findings = [
        Finding("M4", SEVERITY_WARN, "ros", "General", "consolidated"),
        Finding("M8", SEVERITY_FAIL, "ros", "SKIN", "regressed"),
    ]
    rows = report.findings_rows(findings)
    assert rows[0][0] == "M8"
    assert rows[1][0] == "M4"


def test_clause_rows_put_unsupported_first() -> None:
    verdicts = {
        "ros": [
            ClauseVerdict("A", "supported one", PROVENANCE_TEMPLATE, True, "quote", "", ""),
            ClauseVerdict("B", "unsupported one", PROVENANCE_TEMPLATE, False, "", "PE/EXTREMITIES", ""),
        ]
    }
    rows = report.clause_rows(verdicts)
    assert rows[0][4] == "NO"
    assert rows[0][6] == "PE/EXTREMITIES"
    assert rows[1][4] == "yes"


def test_write_report_emits_findings_csv_and_json(seed: ExamMergeCase, tmp_path: Path) -> None:
    findings, metrics = check_case(seed)
    written = report.write_report(tmp_path, findings, metrics)

    assert set(written) == {"findings_csv", "report_json"}
    with written["findings_csv"].open() as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == report.FINDINGS_HEADER
    assert len(rows) == len(findings) + 1

    payload = json.loads(written["report_json"].read_text())
    assert payload["metrics"]["template_name"] == "Subsequent Visit"
    assert "clause_verdicts" not in payload


def test_write_report_emits_clause_csv_when_judged(seed: ExamMergeCase, tmp_path: Path) -> None:
    findings, metrics = check_case(seed)
    verdicts = {"ros": [ClauseVerdict("SKIN", "Denies skin tear", PROVENANCE_TEMPLATE, False, "", "", "")]}
    judge_metrics: dict[str, Any] = {"ros": {"assertions": 1, "unsupported": 1, "unearned_assertion_rate": 1.0}}

    written = report.write_report(tmp_path, findings, metrics, verdicts, judge_metrics)

    assert "clauses_csv" in written
    payload = json.loads(written["report_json"].read_text())
    assert payload["clause_verdicts"]["ros"][0]["supported"] is False
    assert payload["judge_metrics"]["ros"]["unearned_assertion_rate"] == 1.0


def test_format_console_reports_the_clause_counts(seed: ExamMergeCase) -> None:
    findings, metrics = check_case(seed)
    text = report.format_console(findings, metrics)
    assert "template-clauses=" in text
    assert "template-sourced-rows=" in text
    assert "0 fail" in text


def test_format_console_handles_a_no_op_merge() -> None:
    text = report.format_console([], {"case": "x", "template_name": "T", "kinds": []})
    assert "no evaluable merge" in text


# ── reliability ──


def _write_run(directory: Path, name: str, summary: dict[str, Any]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(summary))


def test_load_runs_returns_empty_without_a_runs_directory(seed: ExamMergeCase, tmp_path: Path) -> None:
    assert reliability.load_runs(seed, tmp_path / "absent") == []


def test_compare_runs_needs_two_runs(seed: ExamMergeCase) -> None:
    assert "at least two runs" in reliability.compare_runs([seed])["note"]


def test_compare_runs_detects_unstable_text_and_flipped_flags(seed: ExamMergeCase, tmp_path: Path) -> None:
    variant = json.loads(json.dumps(seed.summary))
    ros = next(c for c in variant["commands"] if c["command_type"] == "ros")
    skin = next(s for s in ros["data"]["sections"] if s["title"] == "SKIN")
    skin["text"] = "Denies rash."
    skin["updated"] = True
    _write_run(tmp_path / "runs", "run_1", seed.summary)
    _write_run(tmp_path / "runs", "run_2", variant)

    runs = reliability.load_runs(seed, tmp_path / "runs")
    comparison = reliability.compare_runs(runs)

    assert comparison["runs"] == 2
    ros_stats = comparison["per_kind"]["ros"]
    assert "skin" in ros_stats["rows_with_unstable_text"]
    assert "skin" in ros_stats["rows_with_flipped_updated_flag"]


def test_compare_runs_reports_finding_recurrence(seed: ExamMergeCase, tmp_path: Path) -> None:
    """A defect present in one run of two should read 1/2 rather than looking systematic."""
    variant = json.loads(json.dumps(seed.summary))
    ros = next(c for c in variant["commands"] if c["command_type"] == "ros")
    skin = next(s for s in ros["data"]["sections"] if s["title"] == "SKIN")
    # Break M1: updated=false while the text no longer matches template_text.
    skin["text"] = "No rashes"
    _write_run(tmp_path / "runs", "run_1", seed.summary)
    _write_run(tmp_path / "runs", "run_2", variant)

    comparison = reliability.compare_runs(reliability.load_runs(seed, tmp_path / "runs"))
    m1 = [e for e in comparison["finding_recurrence"] if e["check_id"] == "M1"]
    assert [e["recurrence"] for e in m1] == ["1/2"]


def test_compare_runs_detects_rows_present_in_only_some_runs(seed: ExamMergeCase, tmp_path: Path) -> None:
    variant = json.loads(json.dumps(seed.summary))
    ros = next(c for c in variant["commands"] if c["command_type"] == "ros")
    ros["data"]["sections"] = [s for s in ros["data"]["sections"] if s["title"] != "OTHER"]
    _write_run(tmp_path / "runs", "run_1", seed.summary)
    _write_run(tmp_path / "runs", "run_2", variant)

    comparison = reliability.compare_runs(reliability.load_runs(seed, tmp_path / "runs"))
    assert comparison["per_kind"]["ros"]["rows_in_some_runs"] == ["other"]
    assert comparison["per_kind"]["ros"]["row_counts"] == [10, 9]


def test_run_from_file_reuses_transcript_and_templates(seed: ExamMergeCase, tmp_path: Path) -> None:
    _write_run(tmp_path / "runs", "run_7", seed.summary)
    run = ExamMergeCase.run_from_file(seed, tmp_path / "runs" / "run_7.json")
    assert run.name.endswith("/run_7")
    assert run.transcript is seed.transcript
    assert run.visit_templates is seed.visit_templates


def test_format_console_for_reliability(seed: ExamMergeCase, tmp_path: Path) -> None:
    _write_run(tmp_path / "runs", "run_1", seed.summary)
    _write_run(tmp_path / "runs", "run_2", seed.summary)
    comparison = reliability.compare_runs(reliability.load_runs(seed, tmp_path / "runs"))
    text = reliability.format_console(comparison)
    assert "2 runs" in text
    assert "finding recurrence" in text
    assert "2/2" in text


def test_format_console_for_single_run(seed: ExamMergeCase) -> None:
    assert "at least two runs" in reliability.format_console(reliability.compare_runs([seed]))
