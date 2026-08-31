"""Render exam-merge evaluation output as CSV and JSON.

Column names follow the existing ``eval_report.csv`` convention in
``evaluations/cases/synthetic_unit_cases/`` so the analysis notebooks read the same
way, with the merge-specific columns appended rather than replacing anything.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from evaluations.exam_merge.invariants import SEVERITY_FAIL, SEVERITY_WARN, Finding
from evaluations.structures.clause_verdict import ClauseVerdict

FINDINGS_HEADER = ["Check", "Severity", "Kind", "Row", "Message"]
CLAUSE_HEADER = ["Kind", "Row", "Assertion", "Provenance", "Supported", "Citation", "Contradicted By", "Note"]


def findings_rows(findings: list[Finding]) -> list[list[str]]:
    order = {SEVERITY_FAIL: 0, SEVERITY_WARN: 1}
    ranked = sorted(findings, key=lambda f: (order.get(f.severity, 2), f.check_id, f.kind, f.row))
    return [[f.check_id, f.severity, f.kind, f.row, f.message] for f in ranked]


def clause_rows(verdicts_by_kind: dict[str, list[ClauseVerdict]]) -> list[list[str]]:
    rows: list[list[str]] = []
    for kind, verdicts in verdicts_by_kind.items():
        # Unsupported first: that is what a reviewer is opening the file to read.
        for verdict in sorted(verdicts, key=lambda v: (v.supported, v.row)):
            rows.append(
                [
                    kind,
                    verdict.row,
                    verdict.assertion,
                    verdict.provenance,
                    "yes" if verdict.supported else "NO",
                    verdict.transcript_citation,
                    verdict.contradicted_by,
                    verdict.note,
                ]
            )
    return rows


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_report(
    directory: Path,
    findings: list[Finding],
    metrics: dict[str, Any],
    verdicts_by_kind: dict[str, list[ClauseVerdict]] | None = None,
    judge_metrics_by_kind: dict[str, Any] | None = None,
) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    findings_path = directory / "merge_findings.csv"
    write_csv(findings_path, FINDINGS_HEADER, findings_rows(findings))
    written["findings_csv"] = findings_path

    payload: dict[str, Any] = {
        "metrics": metrics,
        "findings": [f.to_json() for f in findings],
    }
    if judge_metrics_by_kind:
        payload["judge_metrics"] = judge_metrics_by_kind
    if verdicts_by_kind:
        payload["clause_verdicts"] = {k: [v.to_json() for v in vs] for k, vs in verdicts_by_kind.items()}
        clause_path = directory / "merge_clauses.csv"
        write_csv(clause_path, CLAUSE_HEADER, clause_rows(verdicts_by_kind))
        written["clauses_csv"] = clause_path

    json_path = directory / "merge_report.json"
    with json_path.open("w") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    written["report_json"] = json_path
    return written


def format_console(
    findings: list[Finding],
    metrics: dict[str, Any],
    judge_metrics_by_kind: dict[str, Any] | None = None,
) -> str:
    lines = [f"case: {metrics.get('case', '')}   template: {metrics.get('template_name', '')!r}", ""]
    if not metrics.get("kinds"):
        lines.append("no evaluable merge in this artifact")
    for kind in metrics.get("kinds", []):
        share = kind["template_clause_share"]
        share_text = f"{share:.0%}" if share is not None else "n/a"
        lines.append(
            f"{kind['kind']:<18} template={kind['template_rows']:<3} encounter={kind['encounter_rows']:<3} "
            f"final={kind['final_rows']:<3} template-clauses={kind['template_clauses']}/"
            f"{kind['total_clauses']} ({share_text})"
        )
        lines.append(
            f"{'':<18} template-sourced-rows={kind['template_sourced_rows']} "
            f"(row count undercounts; clauses are what the UI reads)  "
            f"rows-missing-template-text={kind['rows_missing_template_text']}"
        )
        if judge_metrics_by_kind and kind["kind"] in judge_metrics_by_kind:
            judged = judge_metrics_by_kind[kind["kind"]]
            unearned = judged["unearned_assertion_rate"]
            unearned_text = f"{unearned:.0%}" if unearned is not None else "n/a"
            lines.append(
                f"{'':<18} assertions={judged['assertions']} unsupported={judged['unsupported']} "
                f"({unearned_text}) template-sourced-unsupported={judged['template_sourced_unsupported']} "
                f"contradictions={judged['contradictions']}"
            )

    fails = [f for f in findings if f.severity == SEVERITY_FAIL]
    warns = [f for f in findings if f.severity == SEVERITY_WARN]
    lines.append("")
    lines.append(f"{len(fails)} fail, {len(warns)} warn")
    for finding in fails + warns:
        target = f"{finding.kind}/{finding.row}" if finding.row else finding.kind
        lines.append(f"  [{finding.severity:<4}] {finding.check_id} {target}: {finding.message}")
    return "\n".join(lines)
