"""Tests for the Assess Condition background carry-forward.

The helper under test, ``carry_forward_assess_background``, pre-fills the
``background`` field on a new assess proposal using the value from the
patient's most recent prior signed Assessment for the same condition.

These tests pin the six scenarios required by KOALA-5598:
1. Happy path — prior signed note with non-empty background carries forward.
2. No prior note — proposal's background stays empty/unset.
3. Prior background was empty-string — still carried forward as "".
4. Multiple prior signed notes — most recent wins.
5. Different patient with same condition_id — no carry-forward.
6. Voided (entered_in_error) prior — falls back to the most recent
   non-voided prior; if none, no carry-forward.

Plus structural safety tests:
- Provider already typed a background — preserve it.
- Proposal has no condition_id — skip the lookup.
- Note has no patient — skip the lookup.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

from canvas_sdk.test_utils import factories
from canvas_sdk.v1.data.assessment import Assessment
from canvas_sdk.v1.data.condition import Condition, ConditionCoding
from canvas_sdk.v1.data.note import CurrentNoteStateEvent, NoteStates

from hyperscribe.scribe.commands.ap_split import split_plan_into_diagnoses
from hyperscribe.scribe.commands.builder import prefill_diagnose_backgrounds
from hyperscribe.scribe.commands.carry_forward import (
    carry_forward_assess_background,
)


_UNSET = object()


def _make_note(*, patient: Any = _UNSET, note_id: str = "current-note-uuid") -> MagicMock:
    """Build a Note-like double with a patient attribute and id.

    Use ``patient=None`` to force the missing-patient branch; the default
    sentinel gives a fresh MagicMock so the helper proceeds with the lookup.
    """
    note = MagicMock()
    note.patient = MagicMock() if patient is _UNSET else patient
    note.id = note_id
    return note


def _patch_assessment_queryset(prior_background: Any) -> Any:
    """Patch ``Assessment.objects`` to short-circuit the lookup chain.

    The helper builds the queryset:
        Assessment.objects
            .filter(...)
            .exclude(...)
            .order_by(...)
            .values_list("background", flat=True)
            .first()
    so we mock that whole chain to return ``prior_background``. ``None``
    means "no prior row found".
    """
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.order_by.return_value = qs
    qs.values_list.return_value = qs
    qs.first.return_value = prior_background
    return patch(
        "hyperscribe.scribe.commands.carry_forward.Assessment.objects",
        qs,
    )


def test_carry_forward_happy_path_fills_background() -> None:
    """Prior signed note with non-empty background populates the proposal."""
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": None}
    note = _make_note()
    with _patch_assessment_queryset("Diagnosed 2020-05-12; controlled on metformin"):
        carry_forward_assess_background(data, note)
    assert data["background"] == "Diagnosed 2020-05-12; controlled on metformin"


def test_carry_forward_no_prior_leaves_background_empty() -> None:
    """No prior signed assessment exists for this (patient, condition); proposal stays unset."""
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": None}
    note = _make_note()
    with _patch_assessment_queryset(None):
        carry_forward_assess_background(data, note)
    # We intentionally leave the original value (None) untouched when no
    # prior is found — the parser will coerce None to "" downstream.
    assert data["background"] is None


def test_carry_forward_prior_empty_string_still_carried() -> None:
    """If the prior assessment's background was empty, we still propagate "".

    Rationale: empty-string is a valid carried value (the provider may have
    explicitly cleared it in the prior note); skipping it would let stale
    state from earlier notes leak forward through inaction.
    """
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": None}
    note = _make_note()
    with _patch_assessment_queryset(""):
        carry_forward_assess_background(data, note)
    assert data["background"] == ""


def test_carry_forward_most_recent_wins() -> None:
    """The query orders by ``-note__datetime_of_service``, so ``.first()``
    is the most recent. This test pins that contract by inspecting the
    actual ``order_by`` call rather than re-mocking a multi-row fixture.
    """
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": None}
    note = _make_note()
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.order_by.return_value = qs
    qs.values_list.return_value = qs
    qs.first.return_value = "Most recent background"
    with patch(
        "hyperscribe.scribe.commands.carry_forward.Assessment.objects",
        qs,
    ):
        carry_forward_assess_background(data, note)
    assert data["background"] == "Most recent background"
    # Pin the ordering so a refactor can't silently reverse it.
    qs.order_by.assert_called_once_with("-note__datetime_of_service", "-modified")


def test_carry_forward_filters_by_patient_and_condition() -> None:
    """The filter is scoped by (patient, condition, signed, committed, not-voided).

    A different patient with the same condition_id must NOT carry forward.
    We assert this structurally by inspecting the filter kwargs — if the
    scope ever loosens (e.g. dropping ``patient=`` from the filter) this
    test fails.
    """
    patient = MagicMock(name="current-patient")
    data: dict[str, Any] = {"condition_id": "cond-uuid-X", "background": None}
    note = _make_note(patient=patient, note_id="note-uuid-current")
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.order_by.return_value = qs
    qs.values_list.return_value = qs
    qs.first.return_value = "Background from prior"
    with patch(
        "hyperscribe.scribe.commands.carry_forward.Assessment.objects",
        qs,
    ):
        carry_forward_assess_background(data, note)
    filter_kwargs = qs.filter.call_args.kwargs
    assert filter_kwargs["patient"] is patient
    assert filter_kwargs["condition__id"] == "cond-uuid-X"
    assert filter_kwargs["committer_id__isnull"] is False
    assert filter_kwargs["entered_in_error_id__isnull"] is True
    # We DO NOT filter by note state. The committed gate (committer set, no
    # entered_in_error) is sufficient to scope to finalized assessments — a
    # previous iteration filtered on ``note__current_state__state == SIGNED``
    # which excluded prior notes that progressed past SIGNED to LOCKED /
    # RELOCKED / etc. Pin the absence to catch a re-introduction.
    assert "note__current_state__state" not in filter_kwargs
    # The current note must be excluded (so an in-progress STAGED command on
    # the same note for the same condition can't self-poison the lookup).
    exclude_kwargs = qs.exclude.call_args.kwargs
    assert exclude_kwargs == {"note__id": "note-uuid-current"}


def test_carry_forward_voided_filter_excludes_entered_in_error() -> None:
    """``entered_in_error_id__isnull=True`` excludes voided prior rows.

    Amendment workflow (KOALA-5485) voids the old command and recreates it;
    the void leaves ``entered_in_error_id`` non-null on the original row.
    Our filter must skip those so we land on the most-recent NON-voided row.

    This test pins the filter kwarg directly; if a refactor drops it, the
    helper would silently start picking up voided values.
    """
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": None}
    note = _make_note()
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.order_by.return_value = qs
    qs.values_list.return_value = qs
    qs.first.return_value = "Non-voided value"
    with patch(
        "hyperscribe.scribe.commands.carry_forward.Assessment.objects",
        qs,
    ):
        carry_forward_assess_background(data, note)
    filter_kwargs = qs.filter.call_args.kwargs
    assert filter_kwargs["entered_in_error_id__isnull"] is True


def test_carry_forward_preserves_provider_typed_background() -> None:
    """If the proposal already has a non-empty background, do not overwrite.

    This protects the case where the provider clicked into the field and
    typed something before approving the assess — we must not stomp it.
    """
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": "Provider notes"}
    note = _make_note()
    with _patch_assessment_queryset("Carried-forward value (should not be used)") as mock_qs:
        carry_forward_assess_background(data, note)
    assert data["background"] == "Provider notes"
    # The lookup must short-circuit before issuing the query.
    mock_qs.filter.assert_not_called()  # type: ignore[attr-defined]


def test_carry_forward_skipped_when_condition_id_missing() -> None:
    """No condition_id => no carry-forward (we have nothing to scope to).

    This is the unmatched-diagnose path: a diagnose command without an
    ICD-10 match never becomes an assess, so we don't normally hit this
    branch — but defensively the helper must not query a global by-patient
    fallback.
    """
    data: dict[str, Any] = {"condition_id": "", "background": None}
    note = _make_note()
    with _patch_assessment_queryset("Should not be used") as mock_qs:
        carry_forward_assess_background(data, note)
    assert data["background"] is None
    mock_qs.filter.assert_not_called()  # type: ignore[attr-defined]


def test_carry_forward_skipped_when_patient_missing() -> None:
    """Note without a patient => skip (defensive; should not happen in practice)."""
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": None}
    note = _make_note(patient=None)
    with _patch_assessment_queryset("Should not be used") as mock_qs:
        carry_forward_assess_background(data, note)
    assert data["background"] is None
    mock_qs.filter.assert_not_called()  # type: ignore[attr-defined]


def test_carry_forward_runs_when_proposal_background_is_empty_string() -> None:
    """Empty-string background on the proposal is treated as 'not yet set'.

    At proposal-build time we have no signal that distinguishes
    'provider explicitly cleared this' from 'never populated', so the
    conservative choice is to attempt carry-forward whenever the value is
    falsy. The provider can still clear it in the UI before insert.
    """
    data: dict[str, Any] = {"condition_id": "cond-uuid-1", "background": ""}
    note = _make_note()
    with _patch_assessment_queryset("Prior background"):
        carry_forward_assess_background(data, note)
    assert data["background"] == "Prior background"


# --- Integration test (real ORM) ---
#
# Per the project's testing convention (global CLAUDE.md):
#   "At least one test per feature should use the test database (with Factories)."
#
# This repo doesn't use a separate ``@pytest.mark.integration`` marker — the
# ``pytest_canvas`` plugin already autouses the ``db`` fixture for every test —
# so this test is a plain function. It exercises the actual Django ORM chain
# against a real (SQLite test) database, which catches mistakes that
# MagicMock-based tests can't:
#
#   - Filter-kwarg typos (``patient_id=`` vs ``patient=``, ``condition__id`` vs
#     ``condition_id``).
#   - Relation traversal errors (``note__current_state__state`` resolves through
#     a ``OneToOneField`` view-backed model — a refactor breaking the relation
#     would fail here but pass every mock-based test).
#   - The ``str(note.id)`` coercion in ``exclude(note__id=...)`` against a
#     ``UUIDField`` (UUID round-trips that look fine in mocks but mismatch in
#     real SQL).


def test_carry_forward_integration_happy_path() -> None:
    """Integration: a prior signed assessment carries forward via the real ORM.

    Setup:
      - One patient with two notes:
        * ``prior_note``: state SIGNED, with a committed Assessment whose
          ``background`` is a known string.
        * ``current_note``: the "in-progress" note where the new assess
          proposal lives.
      - Both notes reference the same Condition.

    Expectation: ``carry_forward_assess_background`` resolves the prior
    signed Assessment by (patient, condition) and writes its ``background``
    onto the new proposal.

    Why this matters: this is the only test that proves the filter chain
    actually returns the right row from a real DB. Every other test mocks
    ``Assessment.objects``, which means a typo in the filter kwargs would
    pass them all but fail in production.
    """
    patient = factories.PatientFactory.create()
    user = factories.CanvasUserFactory.create()
    prior_note = factories.NoteFactory.create(patient=patient)
    current_note = factories.NoteFactory.create(patient=patient)

    # Advance prior_note to SIGNED via the view-backed CurrentNoteStateEvent.
    # In Postgres this row is materialized by a view; in the SQLite test DB the
    # ``managed=True`` Meta still creates a regular table that we can write
    # directly (verified empirically — see commit message).
    CurrentNoteStateEvent.objects.create(note=prior_note, state=NoteStates.SIGNED)

    condition = Condition.objects.create(
        patient=patient,
        deleted=False,
        onset_date=datetime.date(2024, 1, 1),
        resolution_date=datetime.date(2024, 12, 31),
        clinical_status="active",
        surgical=False,
        committer=user,
    )
    Assessment.objects.create(
        patient=patient,
        note=prior_note,
        condition=condition,
        status="stable",
        narrative="Stable on metformin",
        background="Diagnosed 2020-05-12; controlled on metformin",
        care_team="",
        # ``committer_id`` is the DB pk (``dbid``), per the ID-mapping convention
        # documented in global CLAUDE.md: FK ``_id`` suffix always targets the
        # database primary key, not the externally-exposable id.
        committer_id=user.dbid,
    )

    proposal_data: dict[str, Any] = {
        "condition_id": str(condition.id),
        "background": None,
    }
    carry_forward_assess_background(proposal_data, current_note)

    assert proposal_data["background"] == "Diagnosed 2020-05-12; controlled on metformin"


def test_carry_forward_integration_different_patient_does_not_leak() -> None:
    """Integration: a prior signed assessment for a DIFFERENT patient with the
    SAME ``condition_id`` MUST NOT carry forward.

    Patient cross-pollination would be a hard HIPAA violation: a proposal on
    patient B would pre-fill with patient A's clinical text. This test
    exercises the (patient, condition) scoping against the real ORM so a
    refactor dropping the ``patient=`` filter kwarg can't slip through.
    """
    # Patient A has the prior signed assessment.
    patient_a = factories.PatientFactory.create()
    # Patient B is the one we're building a new proposal for.
    patient_b = factories.PatientFactory.create()
    user = factories.CanvasUserFactory.create()

    prior_note_a = factories.NoteFactory.create(patient=patient_a)
    current_note_b = factories.NoteFactory.create(patient=patient_b)

    CurrentNoteStateEvent.objects.create(note=prior_note_a, state=NoteStates.SIGNED)

    # Shared Condition between the two patients would not normally happen in
    # production (Condition is per-patient), but the carry-forward query
    # filters by ``condition__id`` plus ``patient``. We attach the Condition
    # to patient_a; the ``condition__id`` will resolve, but the ``patient=``
    # scope must reject it for patient_b.
    condition = Condition.objects.create(
        patient=patient_a,
        deleted=False,
        onset_date=datetime.date(2024, 1, 1),
        resolution_date=datetime.date(2024, 12, 31),
        clinical_status="active",
        surgical=False,
        committer=user,
    )
    Assessment.objects.create(
        patient=patient_a,
        note=prior_note_a,
        condition=condition,
        status="stable",
        narrative="Stable",
        # ``background`` is intentionally non-empty so a leak would be visible
        # in the assertion. The content here is fake test data, not PHI — see
        # global CLAUDE.md guidance.
        background="LEAK_CANARY: should never appear on patient B's proposal",
        care_team="",
        committer_id=user.dbid,
    )

    proposal_data: dict[str, Any] = {
        "condition_id": str(condition.id),
        "background": None,
    }
    carry_forward_assess_background(proposal_data, current_note_b)

    # No cross-patient leak: the proposal stays unset.
    assert proposal_data["background"] is None


def test_split_plan_stamp_and_prefill_diagnose_background_integration() -> None:
    """KOALA-5635 integration: end-to-end exercise of the rec-diagnose
    background carry-forward path against the real ORM.

    Setup:
      - One patient with TWO notes:
        * ``prior_note``: state SIGNED, with a committed Assessment on
          condition ``cond_htn`` whose ``background`` is a known string.
        * ``current_note``: the "in-progress" note where the new diagnose
          proposal lives (will be the note passed to ``split_plan_into_diagnoses``).
      - ``cond_htn`` has an ICD-10 coding of ``I10`` so the icd-matching
        in ``_build_active_condition_icd10_index`` picks it up.

    Expectation:
      1. ``split_plan_into_diagnoses(commands, sec, note=current_note)``
         stamps ``data["condition_id"]`` = str(cond_htn.id) on the produced
         diagnose proposal (icd10_code "I10" matches the active condition's
         normalized "I10").
      2. ``prefill_diagnose_backgrounds(commands_list, note_uuid)`` then
         resolves the prior Assessment by (patient, condition_id) and
         carries the background forward onto the proposal's data.

    Why a single integration test instead of two: the two helpers are
    chained in ``post_generate_summary`` (split then prefill); a refactor
    that breaks either one in real ORM terms (typo'd filter kwarg, missing
    coding fetch, stale db_table reference) would fail here. Every other
    test for these helpers mocks the ORM.
    """
    patient = factories.PatientFactory.create()
    user = factories.CanvasUserFactory.create()
    prior_note = factories.NoteFactory.create(patient=patient)
    current_note = factories.NoteFactory.create(patient=patient)

    CurrentNoteStateEvent.objects.create(note=prior_note, state=NoteStates.SIGNED)

    cond_htn = Condition.objects.create(
        patient=patient,
        deleted=False,
        onset_date=datetime.date(2024, 1, 1),
        resolution_date=datetime.date(2024, 12, 31),
        clinical_status="active",
        surgical=False,
        committer=user,
    )
    # Active condition needs an ICD-10 coding for the index lookup to pick
    # it up — the helper filters codings to those whose ``system`` matches
    # /icd/i. Match the home-app FHIR convention.
    ConditionCoding.objects.create(
        condition=cond_htn,
        system="http://hl7.org/fhir/sid/icd-10-cm",
        code="I10",
        display="Essential hypertension",
    )

    Assessment.objects.create(
        patient=patient,
        note=prior_note,
        condition=cond_htn,
        status="stable",
        narrative="Stable on lisinopril",
        background="Diagnosed 2020-03-15; controlled on lisinopril 10mg",
        care_team="",
        committer_id=user.dbid,
    )

    # Simulated post-extract-commands state with a plan command Nabla
    # produced for hypertension. ``section_conditions`` is what
    # ``_match_conditions_to_sections`` would emit in the real flow.
    commands: list[dict[str, Any]] = [
        {
            "command_type": "plan",
            "data": {"narrative": "Hypertension\n- Continue lisinopril 10mg"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Hypertension",
                "coding": [{"code": "I10", "display": "Essential hypertension"}],
            },
        ],
    }

    # Step 1: split — stamps condition_id on the produced diagnose proposal.
    updated, _ = split_plan_into_diagnoses(commands, section_conditions, note=current_note)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["data"]["icd10_code"] == "I10"
    assert updated[0]["data"]["condition_id"] == str(cond_htn.id), (
        "split_plan_into_diagnoses must stamp the SDK condition_id (= "
        "str(condition.id)) on the diagnose proposal when its icd10_code "
        "matches an active condition on the patient. Without the stamp, "
        "the per-(patient, condition) carry-forward short-circuits."
    )

    # Step 2: prefill — resolves the prior signed Assessment by (patient,
    # condition_id) and writes its ``background`` onto the proposal.
    prefill_diagnose_backgrounds(updated, str(current_note.id))
    assert updated[0]["data"]["background"] == "Diagnosed 2020-03-15; controlled on lisinopril 10mg", (
        "prefill_diagnose_backgrounds must carry forward the prior "
        "Assessment.background for the same (patient, condition). A typo in "
        "the filter kwargs or a missing condition_id stamp would fail here "
        "even though every mock-based unit test passes."
    )
