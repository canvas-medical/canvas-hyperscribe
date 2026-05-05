"""Sync Scribe-captured CPT->ICD pointers onto the note's BillingLineItem.

When a perform command commits, Canvas has already created its
BillingLineItem. We replay the ICDs the provider checked in the Charges
matrix as the BLI's assessment_ids ("diagnosis pointers") — the canonical
pre-claim path.

Ordering invariant (load-bearing). Hyperscribe's builder.build_effects
runs all originates first, then all commits, in the input commands[]
order. So `commands=[perform, assess]` would produce
`[orig_perform, orig_assess, commit_perform, commit_assess]`, and Canvas
dispatches PERFORM_COMMAND__POST_COMMIT on commit_perform — before
commit_assess runs and the Assessment lands in the DB. To prevent that
race, summary.js's handleInsert sorts the outgoing commands so A&P
(diagnose/assess) ALWAYS precedes perform, regardless of how the user
appended them. With that sort enforced, by the time this handler fires
for a CPT, every relevant Assessment is committed and resolvable.

Translation chain:

    perform.data.linked_icd10_codes (ICD strings stored by the matrix)
        -> Assessment.condition.codings (ICD strings on this note's
           assess commands)
        -> Assessment.id (the "diagnosis pointer")
        -> BillingLineItem.assessment_ids

Diagnosis rank is unrelated and flows for free via origination order in
builder.build_effects.
"""

from __future__ import annotations

from canvas_sdk.effects import Effect
from canvas_sdk.effects.billing_line_item import UpdateBillingLineItem
from canvas_sdk.events import EventType
from canvas_sdk.handlers.base import BaseHandler
from canvas_sdk.v1.data.assessment import Assessment
from canvas_sdk.v1.data.billing import BillingLineItem
from canvas_sdk.v1.data.command import Command

from logger import log

from hyperscribe.models.scribe import ScribeSummary


def _strip(code: str) -> str:
    """Normalize an ICD-10 code for set-membership comparison.

    The Scribe UI stores dotted form ('E11.9'); ConditionCoding.code may be
    stored either dotted or undotted depending on the source. Strip dots
    and uppercase so both forms compare equal.
    """
    return (code or "").strip().replace(".", "").upper()


class ClaimLinkSync(BaseHandler):
    """On perform-command commit, write the matrix's ICD links to the BLI's assessment_ids."""

    RESPONDS_TO = [EventType.Name(EventType.PERFORM_COMMAND__POST_COMMIT)]

    def compute(self) -> list[Effect]:
        command_id = self.event.target.id if self.event and self.event.target else None
        if not command_id:
            return []

        try:
            cmd = Command.objects.select_related("note").get(id=command_id)
        except Command.DoesNotExist:
            return []

        # Pull the CPT off the just-committed perform command. Canvas stores
        # it under data["perform"]["value"].
        cpt = ((cmd.data or {}).get("perform") or {}).get("value")
        if not cpt:
            return []

        note = cmd.note
        if not note:
            return []

        # Only act on Scribe-managed notes.
        summary = ScribeSummary.objects.filter(note_id=note.dbid).first()
        if not summary or not summary.commands:
            return []

        # Find the matching perform proposal(s) in the matrix payload and
        # collect every linked ICD they declared, preserving the provider's
        # click/rank order. Order is load-bearing: BillingLineItem.assessment_ids
        # IS the diagnosis-pointer sequence on CMS-1500 box 24E, where
        # position 1 is the primary diagnosis for the line item and drives
        # medical-necessity edits, payer routing, and primary-dx-driven
        # reimbursement. The frontend's `handleToggleCptLink` writes
        # `next = [...current, icdCode]` to preserve click order; this loop
        # must propagate that ordering all the way to `assessment_ids` —
        # using a `set` here would destroy it via hash-randomized iteration.
        wanted: list[str] = []
        seen: set[str] = set()
        for entry in summary.commands:
            if entry.get("command_type") != "perform":
                continue
            d = entry.get("data") or {}
            if d.get("cpt_code") != cpt:
                continue
            links = d.get("linked_icd10_codes")
            if not isinstance(links, list):
                continue
            for c in links:
                stripped = _strip(c)
                if stripped and stripped not in seen:
                    seen.add(stripped)
                    wanted.append(stripped)
        if not wanted:
            # Provider didn't link this CPT to anything in the matrix —
            # leave the BLI as-is rather than silently unlinking defaults.
            return []

        # Build ICD-code -> Assessment id map from this note's assessments.
        # Each Assessment hangs off a Condition whose `codings` carry the
        # ICD-10 code. System strings vary across Canvas internals so we
        # match purely on normalized code rather than filtering by system.
        # `prefetch_related("condition__codings")` collapses the per-assessment
        # codings lookup (would be N+1) into a single batched query.
        icd_to_assessment: dict[str, str] = {}
        assessments = (
            Assessment.objects.filter(note_id=note.dbid)
            .select_related("condition")
            .prefetch_related("condition__codings")
        )
        for assess in assessments:
            cond = assess.condition
            if not cond:
                continue
            for coding in cond.codings.all():
                stripped = _strip(coding.code or "")
                if stripped and stripped not in icd_to_assessment:
                    icd_to_assessment[stripped] = str(assess.id)

        target_assessment_ids = [icd_to_assessment[icd] for icd in wanted if icd in icd_to_assessment]
        if not target_assessment_ids:
            log.info(
                "ClaimLinkSync: cpt=%s wanted=%s no matching Assessments on note %s",
                cpt, wanted, note.id,
            )
            return []

        # Find the BillingLineItem(s) for this CPT on this note. Typically one.
        bli_ids = list(
            BillingLineItem.objects.filter(cpt=cpt, note_id=note.dbid).values_list("id", flat=True)
        )
        if not bli_ids:
            log.info("ClaimLinkSync: cpt=%s no BillingLineItem on note %s", cpt, note.id)
            return []

        effects: list[Effect] = []
        for bli_id in bli_ids:
            effects.append(
                UpdateBillingLineItem(
                    billing_line_item_id=str(bli_id),
                    assessment_ids=target_assessment_ids,
                ).apply()
            )
        log.info(
            "ClaimLinkSync: cpt=%s bli=%d assessments=%d/%d",
            cpt, len(bli_ids), len(target_assessment_ids), len(wanted),
        )
        return effects
