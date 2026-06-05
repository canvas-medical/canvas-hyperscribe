"""Deterministic charge enrichment: resolve diagnosis pointers + modifiers
onto the BillingLineItem each PerformCommand creates.

No event handlers. This runs synchronously from the ``/enrich-charges``
endpoint AFTER charges have committed, so every Assessment and BillingLineItem
already exists when we resolve. See design spec §3-§5.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from canvas_sdk.v1.data.assessment import Assessment

# The Coding system CMS modifiers are expressed under. Matches the Canvas SDK
# billing-line-item effect docs example. VERIFY ON INSTANCE (spec §9.3) before
# relying on this exact string.
CPT_MODIFIER_SYSTEM = "http://www.ama-assn.org/go/cpt"


def _normalize_icd10(code: str | None) -> str:
    return (code or "").strip().replace(".", "").upper()


def build_assessment_index(note: Any) -> dict[str, list[str]]:
    """Map normalized ICD-10 code -> [Assessment.id, ...] for the note.

    Excludes entered-in-error assessments. The default Assessment manager
    already filters ``deleted=False`` (AuditedModel). ``prefetch_related`` on
    ``condition__codings`` collapses the per-assessment coding reads to avoid
    an N+1.
    """
    index: dict[str, list[str]] = defaultdict(list)
    assessments = Assessment.objects.filter(
        note=note, entered_in_error__isnull=True
    ).prefetch_related("condition__codings")
    for assessment in assessments:
        condition = assessment.condition
        if condition is None:
            continue
        for coding in condition.codings.all():
            index[_normalize_icd10(coding.code)].append(str(assessment.id))
    return dict(index)
