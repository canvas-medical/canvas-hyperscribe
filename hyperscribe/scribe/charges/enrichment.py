"""Deterministic charge enrichment: resolve diagnosis pointers + modifiers
onto the BillingLineItem each PerformCommand creates.

No event handlers. This runs synchronously from the ``/enrich-charges``
endpoint AFTER charges have committed, so every Assessment and BillingLineItem
already exists when we resolve. See design spec §3-§5.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from canvas_sdk.effects import Effect
from canvas_sdk.effects.billing_line_item import RemoveBillingLineItem, UpdateBillingLineItem
from canvas_sdk.v1.data.assessment import Assessment
from canvas_sdk.v1.data.billing import BillingLineItem, BillingLineItemStatus
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

# The Coding system modifiers are expressed under. Matches the Canvas SDK
# billing-line-item effect docs example. VERIFY ON INSTANCE (spec §9.3) before
# relying on this exact string.
# Known gap: GV and GW (in the picker seed) are HCPCS Level II modifiers
# (CMS-owned, not AMA-CPT). They should carry a different system URI once
# confirmed on instance. All modifiers use this URI for now — live UAT passed,
# but branch per-code if Canvas validates the system field on BLI writes.
CPT_MODIFIER_SYSTEM = "http://www.ama-assn.org/go/cpt"


def _normalize_icd10(code: str | None) -> str:
    return (code or "").strip().replace(".", "").upper()


def build_assessment_index(note: Any) -> dict[str, list[str]]:
    """Map normalized ICD-10 code -> [Assessment.id, ...] for the note.

    Excludes entered-in-error AND soft-deleted assessments. Note that
    ``Assessment.objects`` is Django's plain manager — unlike ``Condition`` it
    does NOT opt into the SDK's ``deleted=False``-filtering manager, so we must
    filter ``deleted=False`` explicitly or a soft-deleted diagnosis would resolve
    and get linked onto a BillingLineItem. ``prefetch_related`` on
    ``condition__codings`` collapses the per-assessment coding reads to avoid
    an N+1.
    """
    index: dict[str, list[str]] = defaultdict(list)
    assessments = Assessment.objects.filter(
        note=note, entered_in_error_id__isnull=True, deleted=False
    ).prefetch_related("condition__codings")
    for assessment in assessments:
        condition = assessment.condition
        if condition is None:
            continue
        for coding in condition.codings.all():
            index[_normalize_icd10(coding.code)].append(str(assessment.id))
    return dict(index)


def _resolve_assessment_ids(pointers: list[dict[str, Any]], index: dict[str, list[str]]) -> list[str]:
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
    # Pre-validate the UUID shape. A malformed or empty command_uuid makes the
    # UUIDField lookup raise django ValidationError (NOT DoesNotExist), which the
    # plugin sandbox cannot catch — it would 500 the whole request and abort
    # enrichment for every charge. Guard it the way session_view does for note_uuid.
    try:
        uuid.UUID(str(command_uuid))
    except (ValueError, TypeError, AttributeError):
        log.info("enrich_charges: command_uuid %r is not a valid uuid", command_uuid)
        return None
    try:
        command = Command.objects.get(id=command_uuid)
    except Command.DoesNotExist:
        # The home-app applies the originate+commit effects from /insert-commands
        # asynchronously, so the command may not exist yet on the first attempt;
        # the frontend retries. Log so we can tell timing apart from a real miss.
        log.info("enrich_charges: command %s not present yet", command_uuid)
        return None
    bli = BillingLineItem.objects.filter(
        note=note, command_id=command.dbid, status=BillingLineItemStatus.ACTIVE
    ).first()
    if bli is None:
        # Fallback to the SDK-documented cpt + note lookup in case command_id
        # isn't populated the way we expect. cpt lives in the perform command's
        # data payload (data["perform"]["value"], or data["cpt_code"]).
        data = getattr(command, "data", None) or {}
        cpt = None
        if isinstance(data, dict):
            perform = data.get("perform")
            if isinstance(perform, dict):
                cpt = perform.get("value")
            cpt = cpt or data.get("cpt_code")
        if cpt:
            qs = BillingLineItem.objects.filter(note=note, cpt=cpt, status=BillingLineItemStatus.ACTIVE)
            count = qs.count()
            if count > 1:
                # Multiple ACTIVE BLIs share this CPT — .first() would pick one
                # arbitrarily and write the wrong charge's pointers onto it.
                # Bail so the caller surfaces billing_line_item_not_found instead
                # of silently corrupting a different charge's claim data.
                log.warning(
                    "enrich_charges: ambiguous cpt %s matches %d BLIs on note"
                    " — skipping fallback to avoid silent miswrite",
                    cpt,
                    count,
                )
            else:
                bli = qs.first()
        log.info(
            "enrich_charges: cmd=%s dbid=%s cpt=%s bli_found=%s (command_id miss)",
            command_uuid,
            command.dbid,
            cpt,
            bli is not None,
        )
    return bli


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
    log.info(
        "enrich_charges: note=%s charges=%d removed=%d assessment_codes=%d",
        note_uuid,
        len(charges),
        len(removed_command_uuids),
        len(index),
    )
    effects: list[Effect] = []
    enriched: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for charge in charges:
        command_uuid = charge.get("command_uuid", "")
        bli = _find_billing_line_item(note, command_uuid)
        if bli is None:
            errors.append({"command_uuid": command_uuid, "reason": "billing_line_item_not_found"})
            continue
        raw_pointers = charge.get("diagnosis_pointers") or []
        if raw_pointers:
            # Pointers were sent — resolve them. EVERY sent ICD code must resolve to
            # a live Assessment. Surface no_assessment_resolved if any fails:
            #   * total failure (none resolve) — bad code or BLI/Assessment not yet
            #     committed; the frontend retries then blocks sign.
            #   * partial failure on a multi-pointer charge — one code's Condition
            #     codings haven't been written yet by the async commit while another
            #     code's have. Without this check the truncated assessment_ids would
            #     be written silently, dropping a pointer from the CMS-1500 claim with
            #     no error and no retry. Comparing requested vs resolved code SETS
            #     catches the partial case that `not assessment_ids` alone misses.
            assessment_ids = _resolve_assessment_ids(raw_pointers, index)
            requested_codes = {_normalize_icd10(p.get("icd10_code")) for p in raw_pointers}
            requested_codes.discard("")  # ignore malformed/empty-code pointers
            resolved_codes = {code for code in requested_codes if index.get(code)}
            if not assessment_ids or resolved_codes != requested_codes:
                errors.append({"command_uuid": command_uuid, "reason": "no_assessment_resolved"})
                continue
        else:
            # Empty pointers sent explicitly: advisory-only new charge (BLI already
            # has no links — clearing is a no-op) OR amendment unlink-all (provider
            # removed every pointer, intent is to clear the BLI). Emit the clear
            # without recording an error so sign is never blocked on advisory unlinking.
            assessment_ids = []
        modifier_codes = [str(m) for m in (charge.get("modifiers") or [])]
        modifiers = [{"code": code, "system": CPT_MODIFIER_SYSTEM} for code in modifier_codes]
        effects.append(
            UpdateBillingLineItem(
                billing_line_item_id=str(bli.id),
                assessment_ids=assessment_ids,
                modifiers=modifiers,
            ).apply()
        )
        enriched.append(
            {
                "command_uuid": command_uuid,
                "billing_line_item_id": str(bli.id),
                "assessment_ids": assessment_ids,
                "modifiers": modifier_codes,
            }
        )

    for command_uuid in removed_command_uuids:
        bli = _find_billing_line_item(note, command_uuid)
        if bli is None:
            # BLI already absent — removal is idempotent, not an error.
            continue
        effects.append(RemoveBillingLineItem(billing_line_item_id=str(bli.id)).apply())

    log.info(
        "enrich_charges result: enriched=%d errors=%d effects=%d (%s)",
        len(enriched),
        len(errors),
        len(effects),
        ",".join(f"{e['command_uuid']}:{e['reason']}" for e in errors) or "ok",
    )
    return effects, enriched, errors
