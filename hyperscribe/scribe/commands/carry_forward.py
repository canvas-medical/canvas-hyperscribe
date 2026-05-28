"""Carry-forward helpers for Scribe command proposals.

This module pre-fills fields on new command proposals using values from the
patient's most recent prior signed note, scoped to a structural identifier
(currently: assess.background scoped by condition).

The provider can always edit/clear the carried value before signing; the saved
value is whatever is in the field at sign time.

Why this lives in the Scribe layer (not the canvas-core ``carry_forward``
action): canvas-core's built-in carry-forward returns the most recent commands
of the same schema_key for the same patient (regardless of which condition the
assessment was for). For Assess Condition, the clinically useful behavior is
per-(patient, condition): the *background* for hypertension follows the
hypertension assessment over time, not whichever assess was authored most
recently.
"""

from __future__ import annotations

from typing import Any

from canvas_sdk.v1.data.assessment import Assessment
from canvas_sdk.v1.data.note import Note
from logger import log


def carry_forward_assess_background(
    proposal_data: dict[str, Any],
    note: Note,
) -> None:
    """Mutate ``proposal_data["background"]`` if a prior signed Assessment exists.

    Behavior:
    - Skips entirely if the proposal already has a non-empty ``background``
      (the provider already typed something, or upstream logic already filled
      it). Empty/None counts as "unset"; a literal empty string at this layer
      is treated as not-yet-populated rather than "explicitly cleared" — at
      proposal-build time we have no signal that distinguishes the two, and
      the conservative choice is to favor carry-forward.
    - Skips if ``condition_id`` is missing or empty (no condition to match against).
    - Skips if ``note.patient`` is unset (defensive — should not happen in practice).
    - Looks up the most recent prior committed, non-entered-in-error
      ``Assessment`` for the same (patient, condition). The committed gate
      (``committer`` set, no ``entered_in_error``) is sufficient to scope to
      finalized assessments — we previously also filtered on
      ``note.current_state.state == SIGNED`` but that excluded prior notes
      that progressed past SIGNED into LOCKED / RELOCKED / etc. The current
      note is excluded by uuid.
    - If found, sets ``proposal_data["background"]`` to the prior value
      (``""`` if the prior background was empty). The provider can still
      edit/clear before insert.

    Why a single helper (not a class hook on the parser): the carry-forward
    needs the ``Note`` and patient context, which the parser doesn't have. The
    helper is invoked from ``session_view`` via ``prefill_assess_backgrounds``,
    parallel to ``annotate_duplicates`` — both are proposal transformations the
    endpoint runs before ``build_effects``.

    Why per-(patient, condition) here rather than reusing canvas-core's
    carry-forward action: canvas-core scopes carry-forward by (patient,
    schema_key) and would surface whichever assess was authored most recently,
    regardless of which condition it documented. Assess Condition is the only
    command where per-condition scoping is clinically meaningful today; if a
    future command needs per-(patient, X) scoping with a different ``X``,
    generalize this helper to take the scoping field as a parameter instead of
    copying the body.
    """
    if proposal_data.get("background"):
        # Provider already populated this field; preserve their input.
        return

    condition_id = proposal_data.get("condition_id")
    if not condition_id:
        # No structural identifier — can't scope carry-forward.
        return

    patient = note.patient
    if patient is None:
        return

    try:
        # The carry-forward is best-effort: an ORM error (transient connection
        # blip, schema drift, etc.) must NOT kill the calling endpoint. The
        # docstring promises "missing background just means the provider types
        # it fresh"; honor that by swallowing the error and bailing.
        # ``note.id`` is internal-only and PHI-safe; do NOT log ``condition_id``,
        # ``background``, patient identifiers, or any other clinical content.
        prior = (
            Assessment.objects.filter(
                patient=patient,
                condition__id=condition_id,
                committer_id__isnull=False,
                entered_in_error_id__isnull=True,
            )
            .exclude(note__id=str(note.id))
            .order_by("-note__datetime_of_service", "-modified")
            .values_list("background", flat=True)
            .first()
        )
    except Exception:
        log.exception("carry-forward assess background query failed for note %s", note.id)
        return

    if prior is None:
        # No prior signed assessment for this (patient, condition).
        return

    # ``prior`` is the carried background. An empty string is still a valid
    # carry-forward value (the provider may have explicitly cleared it last
    # time), so we propagate ``""`` rather than skipping.
    proposal_data["background"] = prior
