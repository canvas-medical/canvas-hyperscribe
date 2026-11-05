"""Layer 1: deterministic checks over a saved exam-merge artifact. No LLM, no cost.

The deterministic floor is gone, so the floor-versus-final ledger that used to be the
headline metric went with it. What replaces it is better: the runtime now runs
``validate_merge`` before a merge is accepted, and this layer re-runs the same function
over the saved artifact. A finding here means either the artifact predates the check or
the check is not doing its job.

What this layer CANNOT see: over-attestation inside a row whose text differs from the
template. That needs the clause-level judge in ``judge.py``, which on one measured note
found six unearned template clauses in a physical exam Layer 1 scored as clean.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from evaluations.exam_merge.case import ExamMergeCase, MergeKindData
from hyperscribe.scribe.recommendations.reconciliation import (
    content_words,
    normalize_title,
    overlap_ratio,
    validate_merge,
)

SEVERITY_FAIL = "fail"
SEVERITY_WARN = "warn"
SEVERITY_INFO = "info"

# Coverage thresholds live with the checks; the word-matching itself is imported from the
# plugin so the harness and the runtime validation cannot drift apart.
_M4_OVERLAP_THRESHOLD = 0.5


class Finding(NamedTuple):
    check_id: str
    severity: str
    kind: str
    row: str
    message: str

    def to_json(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "severity": self.severity,
            "kind": self.kind,
            "row": self.row,
            "message": self.message,
        }


def _titles(sections: list[dict[str, Any]]) -> list[str]:
    return [normalize_title(str(s.get("title", ""))) for s in sections]


# ── individual checks ──


def check_provenance_flags(data: MergeKindData) -> list[Finding]:
    """M1/M2: the ``updated`` flag has to agree with text-versus-template_text.

    A row claiming updated=false while its text differs from the template is lying
    about where the content came from, which breaks both the toggle's count and the
    TEMPLATE_DEFAULTS_SIGNED audit metric.
    """
    findings: list[Finding] = []
    for section in data.final_sections:
        title = str(section.get("title", ""))
        template_text = section.get("template_text")
        text = str(section.get("text", ""))
        updated = section.get("updated")
        if template_text is None:
            if updated is False:
                findings.append(
                    Finding(
                        "M2",
                        SEVERITY_FAIL,
                        data.kind,
                        title,
                        "updated=false on a row with no template_text, so it cannot have come from the template",
                    )
                )
            continue
        if updated is False and text.strip() != str(template_text).strip():
            findings.append(
                Finding(
                    "M1",
                    SEVERITY_FAIL,
                    data.kind,
                    title,
                    "updated=false but the text differs from template_text",
                )
            )
        if updated is True and text.strip() == str(template_text).strip():
            findings.append(
                Finding(
                    "M2",
                    SEVERITY_FAIL,
                    data.kind,
                    title,
                    "updated=true but the text is identical to template_text",
                )
            )
    return findings


def check_template_ordering(data: MergeKindData) -> list[Finding]:
    """M3: template-derived rows keep the scaffold's order.

    Order is how a provider reads an exam. The refinement is allowed to consolidate
    and append, but reordering the operator's scaffold is not an improvement.
    """
    template_order = _titles(data.template_sections)
    present = [t for t in _titles(data.final_sections) if t in template_order]
    expected = [t for t in template_order if t in present]
    if present != expected:
        return [
            Finding(
                "M3",
                SEVERITY_WARN,
                data.kind,
                "",
                f"template rows reordered: expected {expected}, got {present}",
            )
        ]
    return []


def check_encounter_coverage(data: MergeKindData) -> list[Finding]:
    """M4: every encounter finding's content survives somewhere in the output.

    Deliberately content-based rather than row-based. The refinement legitimately
    moves findings between rows, as it did lifting flat affect out of NEUROLOGIC into
    PSYCH on the seed case, so requiring the row to survive would flag good work.
    """
    # Titles on both sides; see coverage_gaps in the plugin for why asymmetry misfires.
    haystack = " ".join(f"{s.get('title', '')} {s.get('text', '')}" for s in data.final_sections)
    findings: list[Finding] = []
    for section in data.encounter_sections:
        # Title joins the text: a finding whose text is a bare "none" has no
        # distinguishing words otherwise, which made "Homicidal ideation: none" read as
        # absent when the merge had folded it into SI/HI.
        needle = f"{section.get('title', '')} {section.get('text', '')}"
        if not content_words(needle):
            continue
        overlap = overlap_ratio(needle, haystack)
        if overlap < _M4_OVERLAP_THRESHOLD:
            findings.append(
                Finding(
                    "M4",
                    SEVERITY_FAIL,
                    data.kind,
                    str(section.get("title", "")),
                    f"encounter finding largely absent from the output ({overlap:.0%} of content words survive)",
                )
            )
        elif normalize_title(str(section.get("title", ""))) not in _titles(data.final_sections):
            findings.append(
                Finding(
                    "M4",
                    SEVERITY_WARN,
                    data.kind,
                    str(section.get("title", "")),
                    f"row consolidated away, content survives elsewhere ({overlap:.0%} of content words)",
                )
            )
    return findings


def check_reference_copies(case: ExamMergeCase) -> list[Finding]:
    """M7: the toggle's restore points must be present and independent of ``sections``."""
    findings: list[Finding] = []
    for kind in case.kinds_missing_reference_copies():
        findings.append(
            Finding(
                "M7",
                SEVERITY_FAIL,
                kind,
                "",
                "template and command exist but encounter_sections was never stamped",
            )
        )
    for data in case.merge_kinds():
        if not data.reconciled_sections:
            findings.append(Finding("M7", SEVERITY_FAIL, data.kind, "", "reconciled_sections missing or empty"))
        elif data.reconciled_sections is data.final_sections:
            findings.append(
                Finding("M7", SEVERITY_FAIL, data.kind, "", "reconciled_sections is the same object as sections")
            )
    return findings


def check_clause_coverage(data: MergeKindData) -> list[Finding]:
    """M8: every row's clauses must together account for its text.

    Provider-facing counts read the clauses, so a row whose clauses omit half its text
    silently undercounts unearned template wording. Compared loosely, since the model
    splits on clinical boundaries rather than reproducing the string exactly.
    """
    findings: list[Finding] = []
    with_clauses = [s for s in data.final_sections if s.get("clauses")]
    if not with_clauses:
        # The whole section predates clause provenance. One line, not one per row.
        return [
            Finding(
                "M8",
                SEVERITY_INFO,
                data.kind,
                "",
                "artifact predates clause provenance, so provider-facing counts fall back to row counts",
            )
        ]

    for section in data.final_sections:
        clauses = section.get("clauses") or []
        text = str(section.get("text", ""))
        if not content_words(text):
            continue
        if not clauses:
            findings.append(
                Finding(
                    "M8",
                    SEVERITY_FAIL,
                    data.kind,
                    str(section.get("title", "")),
                    "row has no clause breakdown while its siblings do, so its template wording is uncounted",
                )
            )
            continue
        if overlap_ratio(text, " ".join(str(c.get("text", "")) for c in clauses)) < 0.9:
            findings.append(
                Finding(
                    "M8",
                    SEVERITY_FAIL,
                    data.kind,
                    str(section.get("title", "")),
                    "the row's clauses do not account for its text, so provider-facing counts will be wrong",
                )
            )
    return findings


def check_runtime_validation(data: MergeKindData) -> list[Finding]:
    """M5: re-run the runtime's own validator over the saved artifact.

    Anything it reports should have been rejected at generation time, so a finding here
    means the artifact predates the validator or the validator has a gap.
    """
    return [
        Finding("M5", SEVERITY_FAIL, data.kind, "", error)
        for error in validate_merge(data.final_sections, data.template_sections, data.encounter_sections)
    ]


def kind_metrics(data: MergeKindData) -> dict[str, Any]:
    template_clauses = sum(
        1 for s in data.final_sections for c in (s.get("clauses") or []) if c.get("provenance") == "template"
    )
    total_clauses = sum(len(s.get("clauses") or []) for s in data.final_sections)
    return {
        "kind": data.kind,
        "template_rows": len(data.template_sections),
        "encounter_rows": len(data.encounter_sections),
        "final_rows": len(data.final_sections),
        # Row-level, kept only to show how badly it undercounts against the clause count.
        "template_sourced_rows": sum(
            1 for s in data.final_sections if s.get("updated") is False and s.get("template_text")
        ),
        "template_clauses": template_clauses,
        "total_clauses": total_clauses,
        "template_clause_share": round(template_clauses / total_clauses, 3) if total_clauses else None,
        "rows_missing_template_text": sum(
            1
            for s in data.final_sections
            if s.get("template_text") is None
            and normalize_title(str(s.get("title", "")))
            in {normalize_title(str(t.get("title", ""))) for t in data.template_sections}
        ),
        "template_removed": data.template_removed,
    }


def check_case(case: ExamMergeCase) -> tuple[list[Finding], dict[str, Any]]:
    """Run every Layer 1 check. Returns (findings, metrics)."""
    findings: list[Finding] = list(check_reference_copies(case))
    metrics: dict[str, Any] = {
        "case": case.name,
        "template_name": case.template_name(),
        "kinds": [],
    }

    kinds = case.merge_kinds()
    if not kinds:
        findings.append(
            Finding(
                "M0",
                SEVERITY_INFO,
                "",
                "",
                f"no evaluable merge: template {case.template_name()!r} supplies no scaffold, "
                "or no exam command carries reference copies",
            )
        )
        return findings, metrics

    for data in kinds:
        findings.extend(check_provenance_flags(data))
        findings.extend(check_template_ordering(data))
        findings.extend(check_encounter_coverage(data))
        findings.extend(check_runtime_validation(data))
        findings.extend(check_clause_coverage(data))
        metrics["kinds"].append(kind_metrics(data))

    return findings, metrics
