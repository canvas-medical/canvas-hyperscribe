"""Layer 3: run-to-run stability for the same transcript.

A defect that shows up in 2 of 5 generations is a different problem from one that
shows up in 5 of 5, and right now we cannot tell those apart. This layer replays
``runs/run_N.json`` against the same transcript and templates, then reports what moved.

The deterministic floor needs no run of its own. ``merge_sections`` is pure, so Layer 1
recomputes it for free from any single artifact; the interesting variance is entirely
in what the refinement did on top.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluations.exam_merge.case import ExamMergeCase
from evaluations.exam_merge.invariants import Finding, check_case, normalize_title


def load_runs(base: ExamMergeCase, runs_directory: Path) -> list[ExamMergeCase]:
    if not runs_directory.is_dir():
        return []
    return [ExamMergeCase.run_from_file(base, path) for path in sorted(runs_directory.glob("*.json"))]


def _row_texts(case: ExamMergeCase, kind: str) -> dict[str, str]:
    for data in case.merge_kinds():
        if data.kind == kind:
            return {normalize_title(str(s.get("title", ""))): str(s.get("text", "")) for s in data.final_sections}
    return {}


def _row_updated(case: ExamMergeCase, kind: str) -> dict[str, bool]:
    for data in case.merge_kinds():
        if data.kind == kind:
            return {normalize_title(str(s.get("title", ""))): bool(s.get("updated")) for s in data.final_sections}
    return {}


def _finding_key(finding: Finding) -> tuple[str, str, str]:
    return (finding.check_id, finding.kind, finding.row)


def compare_runs(runs: list[ExamMergeCase]) -> dict[str, Any]:
    """Aggregate stability across runs. Needs at least two to say anything."""
    if len(runs) < 2:
        return {"runs": len(runs), "note": "at least two runs are needed to measure stability"}

    kinds = sorted({data.kind for run in runs for data in run.merge_kinds()})
    per_kind: dict[str, Any] = {}

    for kind in kinds:
        texts = [_row_texts(run, kind) for run in runs]
        flags = [_row_updated(run, kind) for run in runs]
        present = [set(t) for t in texts]
        always = set.intersection(*present) if present else set()
        ever = set.union(*present) if present else set()

        unstable_text = sorted(title for title in always if len({t.get(title, "") for t in texts}) > 1)
        flipped = sorted(title for title in always if len({f.get(title) for f in flags}) > 1)

        per_kind[kind] = {
            "row_counts": [len(t) for t in texts],
            "rows_in_every_run": len(always),
            "rows_in_some_runs": sorted(ever - always),
            "rows_with_unstable_text": unstable_text,
            "rows_with_flipped_updated_flag": flipped,
        }

    # Finding recurrence: a fail present in 5 of 5 is systematic; 1 of 5 is a coin flip.
    recurrence: dict[str, dict[str, Any]] = {}
    for run in runs:
        findings, _ = check_case(run)
        for finding in findings:
            key = "|".join(_finding_key(finding))
            entry = recurrence.setdefault(
                key,
                {
                    "check_id": finding.check_id,
                    "severity": finding.severity,
                    "kind": finding.kind,
                    "row": finding.row,
                    "runs": 0,
                },
            )
            entry["runs"] += 1
    for entry in recurrence.values():
        entry["recurrence"] = f"{entry['runs']}/{len(runs)}"

    return {
        "runs": len(runs),
        "run_names": [run.name for run in runs],
        "per_kind": per_kind,
        "finding_recurrence": sorted(
            recurrence.values(), key=lambda e: (-e["runs"], e["check_id"], e["kind"], e["row"])
        ),
    }


def format_console(comparison: dict[str, Any]) -> str:
    if comparison.get("note"):
        return f"{comparison['runs']} run(s): {comparison['note']}"
    lines = [f"{comparison['runs']} runs: {', '.join(comparison['run_names'])}", ""]
    for kind, stats in comparison["per_kind"].items():
        lines.append(f"{kind}")
        lines.append(f"  row counts across runs: {stats['row_counts']}")
        lines.append(f"  rows present in every run: {stats['rows_in_every_run']}")
        if stats["rows_in_some_runs"]:
            lines.append(f"  rows present in only some runs: {stats['rows_in_some_runs']}")
        if stats["rows_with_unstable_text"]:
            lines.append(f"  rows whose text changed between runs: {stats['rows_with_unstable_text']}")
        if stats["rows_with_flipped_updated_flag"]:
            lines.append(f"  rows whose updated flag flipped: {stats['rows_with_flipped_updated_flag']}")
    lines.append("")
    lines.append("finding recurrence")
    for entry in comparison["finding_recurrence"]:
        target = f"{entry['kind']}/{entry['row']}" if entry["row"] else entry["kind"]
        lines.append(f"  {entry['recurrence']:<6} [{entry['severity']:<4}] {entry['check_id']} {target}")
    return "\n".join(lines)
