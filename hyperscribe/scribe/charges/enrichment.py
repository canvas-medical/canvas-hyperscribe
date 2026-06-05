"""Deterministic charge enrichment: resolve diagnosis pointers + modifiers
onto the BillingLineItem each PerformCommand creates.

No event handlers. This runs synchronously from the ``/enrich-charges``
endpoint AFTER charges have committed, so every Assessment and BillingLineItem
already exists when we resolve. See design spec §3-§5.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from canvas_sdk.effects import Effect
from canvas_sdk.effects.billing_line_item import RemoveBillingLineItem, UpdateBillingLineItem
from canvas_sdk.v1.data.assessment import Assessment
from canvas_sdk.v1.data.billing import BillingLineItem, BillingLineItemStatus
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

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
        note=note, entered_in_error_id__isnull=True
    ).prefetch_related("condition__codings")
    for assessment in assessments:
        condition = assessment.condition
        if condition is None:
            continue
        for coding in condition.codings.all():
            index[_normalize_icd10(coding.code)].append(str(assessment.id))
    return dict(index)


def _resolve_assessment_ids(
    pointers: list[dict[str, Any]], index: dict[str, list[str]]
) -> list[str]:
    """Resolve a charge's diagnosis pointers to Assessment ids via the code
    index. De-duplicates while preserving order. When an ICD code maps to more
    than one assessment (rare: two assessments of the same condition on one
    note), all matches are included and a warning is logged — there is no
    direct Command->Assessment FK to disambiguate further (spec §5)."""
    resolved: list[str] = []
    for pointer in pointers:
        code = _normalize_icd10(pointer.get("icd10_code"))
        matches = index.get(code, [])
        if len(matches) > 1:
            log.warning("enrich_charges: ambiguous icd10 %s maps to %d assessments", code, len(matches))
        for assessment_id in matches:
            if assessment_id not in resolved:
                resolved.append(assessment_id)
    return resolved


def _find_billing_line_item(note: Any, command_uuid: str) -> Any | None:
    """Find the ACTIVE BillingLineItem the given PerformCommand created.

    Matched by ``command_id`` (== Command.dbid) + note + active status. This is
    the precise lookup; the loose ``cpt + note`` match used by PR #257 is
    ambiguous when two charges share a CPT. Returns None if the command or BLI
    can't be found."""
    try:
        command = Command.objects.get(id=command_uuid)
    except Command.DoesNotExist:
        return None
    return (
        BillingLineItem.objects.filter(
            note=note, command_id=command.dbid, status=BillingLineItemStatus.ACTIVE
        ).first()
    )


def build_charge_enrichment_effects(
    charges: list[dict[str, Any]],
    removed_command_uuids: list[str],
    note_uuid: str,
) -> tuple[list[Effect], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build BillingLineItem effects for charge enrichment.

    ``charges`` is the desired enriched state for surviving charges; each is
    ``{command_uuid, diagnosis_pointers:[{command_uuid, icd10_code}], modifiers:[code]}``.
    ``removed_command_uuids`` are PerformCommand uuids whose BLI should be
    removed (amendment charge removal).

    Returns ``(effects, enriched, errors)``. ``enriched`` records what was
    written (for audit/UI); ``errors`` records charges whose BLI couldn't be
    located. Assumes ``charges`` already passed ``validate_charge_enrichment``.
    """
    try:
        note = Note.objects.get(id=note_uuid)
    except Note.DoesNotExist:
        return [], [], [{"command_uuid": "", "reason": "note_not_found"}]

    index = build_assessment_index(note)
    effects: list[Effect] = []
    enriched: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for charge in charges:
        command_uuid = charge.get("command_uuid", "")
        bli = _find_billing_line_item(note, command_uuid)
        if bli is None:
            errors.append({"command_uuid": command_uuid, "reason": "billing_line_item_not_found"})
            continue
        assessment_ids = _resolve_assessment_ids(charge.get("diagnosis_pointers") or [], index)
        modifier_codes = [str(m) for m in (charge.get("modifiers") or [])]
        modifiers = [{"code": code, "system": CPT_MODIFIER_SYSTEM} for code in modifier_codes]
        effects.append(
            UpdateBillingLineItem(
                billing_line_item_id=str(bli.id),
                assessment_ids=assessment_ids,
                modifiers=modifiers,
            ).apply()
        )
        enriched.append({
            "command_uuid": command_uuid,
            "billing_line_item_id": str(bli.id),
            "assessment_ids": assessment_ids,
            "modifiers": modifier_codes,
        })

    for command_uuid in removed_command_uuids:
        bli = _find_billing_line_item(note, command_uuid)
        if bli is None:
            continue
        effects.append(RemoveBillingLineItem(billing_line_item_id=str(bli.id)).apply())

    return effects, enriched, errors
