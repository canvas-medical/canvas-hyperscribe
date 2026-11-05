#!/usr/bin/env uv run
"""Evaluate a saved exam-merge artifact offline.

    DJANGO_SETTINGS_MODULE=settings uv run python -m scripts.exam_merge_eval \
        --case evaluations/cases/exam_merge/subsequent_visit_shoulder_dm

``DJANGO_SETTINGS_MODULE`` is required because the checks import the plugin's own
``merge_sections`` and ``parse_ros_subsections``, which pull in ``canvas_sdk`` and
therefore Django settings. Layer 1 needs nothing else. ``--judge`` additionally needs
``VendorTextLLM`` and ``KeyTextLLM`` from ``local_env.sh``.
"""

from __future__ import annotations

import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from evaluations.exam_merge import reliability, report
from evaluations.exam_merge.case import ExamMergeCase
from evaluations.exam_merge.invariants import SEVERITY_FAIL, check_case
from evaluations.exam_merge.judge import JUDGE_MODEL


class ExamMergeEval:
    @classmethod
    def parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Evaluate a saved visit-template exam merge artifact")
        parser.add_argument("--case", type=Path, required=True, help="case directory")
        parser.add_argument(
            "--judge",
            action="store_true",
            help="also run the clause-level LLM judge (needs VendorTextLLM / KeyTextLLM)",
        )
        parser.add_argument(
            "--judge-model",
            default=None,
            help=f"override the judge model (default {JUDGE_MODEL})",
        )
        parser.add_argument(
            "--reliability",
            action="store_true",
            help="compare the summaries in <case>/runs/ for run-to-run stability",
        )
        parser.add_argument("--out", type=Path, default=None, help="report directory, defaults to <case>/report")
        parser.add_argument(
            "--fail-on-finding",
            action="store_true",
            help="exit 1 when any check fails, for use in CI",
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> int:
        args = cls.parameters()
        if not args.case.is_dir():
            print(f"not a directory: {args.case}")
            return 2

        case = ExamMergeCase.from_directory(args.case)
        findings, metrics = check_case(case)

        verdicts_by_kind = None
        judge_metrics_by_kind = None
        if args.judge:
            from evaluations.exam_merge.judge import judge_case

            verdicts_by_kind, judge_metrics_by_kind = judge_case(case, model=args.judge_model or JUDGE_MODEL)

        print(report.format_console(findings, metrics, judge_metrics_by_kind))

        written = report.write_report(
            args.out or (args.case / "report"),
            findings,
            metrics,
            verdicts_by_kind,
            judge_metrics_by_kind,
        )
        print("")
        for label, path in written.items():
            print(f"{label}: {path}")

        if args.reliability:
            runs = reliability.load_runs(case, args.case / "runs")
            print("")
            print(reliability.format_console(reliability.compare_runs(runs)))

        if args.fail_on_finding and any(f.severity == SEVERITY_FAIL for f in findings):
            return 1
        return 0


if __name__ == "__main__":
    sys.exit(ExamMergeEval.run())
