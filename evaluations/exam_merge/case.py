"""Load a saved exam-merge artifact as a replayable evaluation case.

A case directory holds three inputs, all of which already exist as by-products of
running a note:

    transcript.json       the finalized transcript that was generated from
    visit_templates.json  the value of the VisitTemplates plugin secret
    summary.json          what GET /summary returned afterwards

That is enough to reconstruct the whole merge offline. ``selected_template_name``
in the summary resolves the scaffold out of the VisitTemplates config,
``parse_ros_subsections`` turns the scaffold into template sections, and
``merge_sections`` recomputes the deterministic floor. So the floor, the LLM's
delta, and every provenance invariant cost nothing to check.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NamedTuple

from hyperscribe.scribe.commands.extractor import parse_ros_subsections

# Merge kind -> the VisitTemplates field holding its scaffold. Mirrors
# _EXAM_MERGE_SPECS in hyperscribe/scribe/api/session_view.py.
TEMPLATE_FIELD_BY_KIND: dict[str, str] = {
    "ros": "ros_template",
    "physical_exam": "pe_template",
    "mental_status_exam": "mse_template",
}

# Display labels, matching the label passed to reconcile_sections.
LABEL_BY_KIND: dict[str, str] = {
    "ros": "Review of Systems",
    "physical_exam": "Physical Exam",
    "mental_status_exam": "Mental Status Exam",
}


class MergeKindData(NamedTuple):
    """Everything needed to evaluate one section kind of one artifact."""

    kind: str
    label: str
    template_sections: list[dict[str, str]]
    encounter_sections: list[dict[str, Any]]
    final_sections: list[dict[str, Any]]
    reconciled_sections: list[dict[str, Any]]
    template_removed: bool


class ExamMergeCase:
    def __init__(
        self,
        name: str,
        transcript: dict[str, Any],
        visit_templates: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        self.name = name
        self.transcript = transcript
        self.visit_templates = visit_templates
        self.summary = summary

    @classmethod
    def from_directory(cls, directory: Path) -> ExamMergeCase:
        def load(filename: str) -> dict[str, Any]:
            path = directory / filename
            if not path.exists():
                raise FileNotFoundError(f"{directory.name}: missing {filename}")
            with path.open() as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                raise ValueError(f"{directory.name}/{filename}: expected a JSON object")
            return data

        return cls(
            name=directory.name,
            transcript=load("transcript.json"),
            visit_templates=load("visit_templates.json"),
            summary=load("summary.json"),
        )

    @classmethod
    def run_from_file(cls, base: ExamMergeCase, summary_path: Path) -> ExamMergeCase:
        """A repeat run of the same case: same transcript and templates, new summary.

        Used by the reliability layer, where ``runs/run_N.json`` holds only the
        summary because the other two inputs are identical by construction.
        """
        with summary_path.open() as handle:
            summary = json.load(handle)
        return cls(
            name=f"{base.name}/{summary_path.stem}",
            transcript=base.transcript,
            visit_templates=base.visit_templates,
            summary=summary,
        )

    # ── inputs ──

    def template_name(self) -> str:
        return str(self.summary.get("selected_template_name") or "")

    def template_config(self) -> dict[str, Any]:
        """The VisitTemplates entry the operator selected, or {} when unresolvable."""
        wanted = self.template_name()
        for entry in self.visit_templates.get("templates", []):
            if isinstance(entry, dict) and entry.get("name") == wanted:
                return entry
        return {}

    def template_sections(self, kind: str) -> list[dict[str, str]]:
        """Parse the scaffold exactly as _load_templates does at generation time.

        A null or absent field yields [], which is the "merge did not apply to this
        kind" case rather than an error.
        """
        raw = self.template_config().get(TEMPLATE_FIELD_BY_KIND[kind])
        if not raw:
            return []
        return parse_ros_subsections(str(raw))

    def command(self, kind: str) -> dict[str, Any] | None:
        for command in self.summary.get("commands", []):
            if isinstance(command, dict) and command.get("command_type") == kind:
                return command
        return None

    def merge_kinds(self) -> list[MergeKindData]:
        """Every kind where a merge is evaluable: a template AND a command both exist."""
        result: list[MergeKindData] = []
        for kind in TEMPLATE_FIELD_BY_KIND:
            template_sections = self.template_sections(kind)
            command = self.command(kind)
            if not template_sections or command is None:
                continue
            data = command.get("data") or {}
            encounter = data.get("encounter_sections")
            if not isinstance(encounter, list):
                # Step 2.5 did not write the reference copies, so the merge either
                # did not run for this kind or predates the feature. Nothing to
                # evaluate, and _no_reference_copies reports it as a finding.
                continue
            result.append(
                MergeKindData(
                    kind=kind,
                    label=LABEL_BY_KIND[kind],
                    template_sections=template_sections,
                    encounter_sections=encounter,
                    final_sections=data.get("sections") or [],
                    reconciled_sections=data.get("reconciled_sections") or [],
                    template_removed=bool(data.get("template_removed")),
                )
            )
        return result

    def kinds_missing_reference_copies(self) -> list[str]:
        """Kinds with a template and a command but no encounter_sections stamped."""
        missing: list[str] = []
        for kind in TEMPLATE_FIELD_BY_KIND:
            command = self.command(kind)
            if not self.template_sections(kind) or command is None:
                continue
            if not isinstance((command.get("data") or {}).get("encounter_sections"), list):
                missing.append(kind)
        return missing

    # ── transcript ──

    def transcript_lines(self) -> list[str]:
        lines: list[str] = []
        for item in self.transcript.get("items", []):
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if text:
                lines.append(f"{item.get('speaker', 'UNSPECIFIED')}: {text}")
        return lines

    def transcript_text(self) -> str:
        return "\n".join(self.transcript_lines())

    def note_sections(self) -> list[dict[str, str]]:
        """Note sections, for cross-section contradiction checks."""
        sections = (self.summary.get("note_data") or {}).get("sections") or []
        return [s for s in sections if isinstance(s, dict)]
