import json
from typing import Any

import pytest
from unittest.mock import MagicMock, patch

from canvas_generated.messages.effects_pb2 import EffectType
from pydantic import BaseModel, Field, ValidationError

from hyperscribe.scribe.commands.builder import (
    _format_pydantic_errors,
    build_effects,
    build_metadata_effects,
    prefill_assess_backgrounds,
    validate_proposals,
)


def _make_constrained_int_model(
    ge: int | None = None,
    le: int | None = None,
    gt: int | None = None,
    lt: int | None = None,
) -> type[BaseModel]:
    """Build a tiny Pydantic v2 model with the requested numeric constraint on ``value``.

    Used by the type-string guard test to exercise each branch of
    ``_format_pydantic_errors`` against a real ValidationError, not a synthesized dict.
    """
    field_kwargs: dict[str, Any] = {}
    if ge is not None:
        field_kwargs["ge"] = ge
    if le is not None:
        field_kwargs["le"] = le
    if gt is not None:
        field_kwargs["gt"] = gt
    if lt is not None:
        field_kwargs["lt"] = lt

    class _NumModel(BaseModel):
        value: int = Field(**field_kwargs)

    return _NumModel


def _make_constrained_str_model(
    min_length: int | None = None,
    max_length: int | None = None,
) -> type[BaseModel]:
    """Build a Pydantic v2 model with a string-length constraint on ``value``."""
    field_kwargs: dict[str, Any] = {}
    if min_length is not None:
        field_kwargs["min_length"] = min_length
    if max_length is not None:
        field_kwargs["max_length"] = max_length

    class _StrModel(BaseModel):
        value: str = Field(**field_kwargs)

    return _StrModel


def _make_required_field_model() -> type[BaseModel]:
    """Build a Pydantic v2 model with a required field (no default) to trigger
    ``type=missing``."""

    class _ReqModel(BaseModel):
        value: int

    return _ReqModel


def test_build_effects_routes_all_types() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "rfv", "data": {"comment": "Headache"}},
        {"command_type": "hpi", "data": {"narrative": "Two weeks of headaches"}},
        {"command_type": "vitals", "data": {"pulse": 72, "blood_pressure_systole": 120, "blood_pressure_diastole": 80}},
        {"command_type": "plan", "data": {"narrative": "Start sumatriptan"}},
        {"command_type": "medication_statement", "data": {"medication_text": "Lisinopril 10mg"}},
        {"command_type": "task", "data": {"title": "Follow up"}},
        {"command_type": "prescribe", "data": {"fdb_code": "123", "sig": "daily"}},
        {"command_type": "lab_order", "data": {"comment": "CBC"}},
        {"command_type": "imaging_order", "data": {"comment": "MRI", "priority": "Routine"}},
        {
            "command_type": "history_review",
            "data": {"sections": [{"key": "past_medical_history", "title": "PMH", "text": "HTN"}]},
        },
        {
            "command_type": "chart_review",
            "data": {"sections": [{"key": "allergies", "title": "Allergies", "text": "NKDA"}]},
        },
        {
            "command_type": "allergy",
            "data": {"allergy_text": "Penicillin", "concept_id": None, "concept_id_type": None},
        },
        {
            "command_type": "diagnose",
            "data": {"icd10_code": "G43.009", "today_assessment": "Start sumatriptan"},
        },
        {
            "command_type": "assess",
            "data": {"condition_id": "cond-uuid", "narrative": "Stable"},
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv,
        patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.plan.PlanCommand") as mock_plan,
        patch("hyperscribe.scribe.commands.vitals.VitalsCommand") as mock_vitals,
        patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med,
        patch("hyperscribe.scribe.commands.task.TaskCommand") as mock_task,
        patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_rx,
        patch("hyperscribe.scribe.commands.lab_order.LabOrderCommand") as mock_lab,
        patch("hyperscribe.scribe.commands.imaging_order.ImagingOrderCommand") as mock_img,
        patch("hyperscribe.scribe.commands.history_review.render_to_string", return_value=""),
        patch("hyperscribe.scribe.commands.chart_review.render_to_string", return_value=""),
        patch("hyperscribe.scribe.commands.history_review.CustomCommand") as mock_history,
        patch("hyperscribe.scribe.commands.chart_review.CustomCommand") as mock_chart,
        patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_allergy,
        patch("hyperscribe.scribe.commands.diagnose.DiagnoseCommand") as mock_diagnose,
        patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_assess,
    ):
        all_mocks = [
            mock_rfv,
            mock_hpi,
            mock_plan,
            mock_vitals,
            mock_med,
            mock_task,
            mock_rx,
            mock_lab,
            mock_img,
            mock_history,
            mock_chart,
            mock_allergy,
            mock_diagnose,
            mock_assess,
        ]
        for mock in all_mocks:
            inst = MagicMock()
            inst.originate.return_value = f"{mock._mock_name}_originate"
            inst.commit.return_value = f"{mock._mock_name}_commit"
            inst.review.return_value = f"{mock._mock_name}_review"
            inst.command_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
            inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
            mock.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        )

    # 14 originates + 13 commits + 1 review (prescription)
    assert len(effects) == 28
    assert metadata_pending == []
    assert len(attempted) == 14
    assert {a["command_type"] for a in attempted} == {
        "rfv",
        "hpi",
        "vitals",
        "plan",
        "medication_statement",
        "task",
        "prescribe",
        "lab_order",
        "imaging_order",
        "history_review",
        "chart_review",
        "allergy",
        "diagnose",
        "assess",
    }
    for mock in all_mocks:
        mock.assert_called_once()


def test_build_effects_unknown_type_skipped() -> None:
    proposals: list[dict[str, Any]] = [{"command_type": "unknown_type", "data": {"foo": "bar"}}]
    effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []


def test_build_effects_empty_list() -> None:
    effects, metadata_pending, attempted, build_errors = build_effects([], "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []


def test_prefill_assess_backgrounds_filters_assess_only_and_loads_note() -> None:
    """``prefill_assess_backgrounds`` filters to assess proposals, loads the
    ``Note``, and delegates to ``carry_forward_assess_background`` per
    proposal.

    This pins the public-function contract: non-assess proposals are skipped
    (no DB lookup chain runs for them), and proposals with non-dict ``data``
    are tolerated without raising.
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "assess", "data": {"condition_id": "cond-1", "background": None}},
        {"command_type": "plan", "data": {"narrative": "Start naproxen"}},
        # Defensive: malformed proposal must not crash the loop.
        {"command_type": "assess", "data": None},
    ]
    fake_note = MagicMock()
    fake_note.id = "note-uuid-1"
    with (
        patch("hyperscribe.scribe.commands.builder.Note.objects") as mock_note_qs,
        patch("hyperscribe.scribe.commands.builder.carry_forward_assess_background") as mock_carry,
    ):
        mock_note_qs.select_related.return_value.get.return_value = fake_note
        prefill_assess_backgrounds(proposals, "note-uuid-1")
    # Only one valid assess proposal (the one with a dict ``data``) is delegated.
    mock_carry.assert_called_once_with(proposals[0]["data"], fake_note)


def test_prefill_assess_backgrounds_silent_on_malformed_note_uuid() -> None:
    """A non-UUID ``note_uuid`` must NOT raise — the carry-forward is
    best-effort and a malformed identifier should silently skip the
    convenience, not blow up the calling endpoint.

    Django raises ``ValueError`` (not ``Note.DoesNotExist``) for a malformed
    UUID before reaching the SQL layer; both must be swallowed.
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "assess", "data": {"condition_id": "cond-1", "background": None}},
    ]
    with (
        patch("hyperscribe.scribe.commands.builder.Note.objects") as mock_note_qs,
        patch("hyperscribe.scribe.commands.builder.carry_forward_assess_background") as mock_carry,
    ):
        mock_note_qs.select_related.return_value.get.side_effect = ValueError(
            "badly formed hexadecimal UUID string",
        )
        # Must not raise.
        prefill_assess_backgrounds(proposals, "not-a-uuid")
    mock_carry.assert_not_called()
    # The background on the proposal is left untouched.
    assert proposals[0]["data"]["background"] is None


def test_prefill_assess_backgrounds_no_assess_proposals_short_circuits() -> None:
    """If there are no assess proposals, skip the Note lookup entirely.

    This is an N+1 / latency guard: a request with only non-assess commands
    should not pay for the ``Note.objects.select_related("patient").get(...)``
    query.
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "plan", "data": {"narrative": "Start naproxen"}},
    ]
    with patch("hyperscribe.scribe.commands.builder.Note.objects") as mock_note_qs:
        prefill_assess_backgrounds(proposals, "note-uuid-1")
    mock_note_qs.select_related.assert_not_called()


def test_build_effects_no_longer_calls_prefill_assess_backgrounds() -> None:
    """``build_effects`` is symmetric with ``annotate_duplicates`` — both
    are called by ``session_view`` at the same layer, NOT from inside
    ``build_effects``. This test pins that placement so a future refactor
    can't silently re-hide the carry-forward inside ``build_effects``.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "assess",
            "data": {
                "condition_id": "cond-uuid-abc",
                "narrative": "Stable today",
                "background": "Provider-typed",
            },
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.builder.prefill_assess_backgrounds") as mock_prefill,
        patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_assess,
    ):
        inst = MagicMock()
        inst.originate.return_value = "assess_originate"
        inst.commit.return_value = "assess_commit"
        inst.command_uuid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        mock_assess.return_value = inst

        build_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

        # Symmetry guard: ``build_effects`` does not call the carry-forward.
        # The caller (session_view) is responsible.
        mock_prefill.assert_not_called()


def test_build_effects_medication_with_alert_facility_emits_yes_inline() -> None:
    """Flag on + alert_facility True: originate, UPSERT_COMMAND_METADATA="Yes" inline, commit.

    Pins the exact protobuf payload so any SDK schema change for
    UPSERT_COMMAND_METADATA breaks CI rather than silently diverging.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg", "alert_facility": True},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        inst = MagicMock()
        inst.originate.return_value = "med_originate"
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "d6a96b19-a087-458a-9619-b46537a8c121"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        inst.Meta.key = "medicationStatement"
        mock_med.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            feature_flags={"AlertFacilityEnabled": True},
        )

    assert len(effects) == 3
    assert effects[0] == "med_originate"
    assert effects[2] == "med_commit"
    meta_effect = effects[1]
    assert EffectType.Name(meta_effect.type) == "UPSERT_COMMAND_METADATA"
    assert json.loads(meta_effect.payload) == {
        "data": {
            "schema_key": "medicationStatement",
            "command_id": "d6a96b19-a087-458a-9619-b46537a8c121",
            "key": "alert_facility",
            "value": "Yes",
        },
    }
    assert metadata_pending == []
    assert len(attempted) == 1
    assert attempted[0]["command_type"] == "medication_statement"


def test_build_effects_medication_alert_facility_false_writes_no_inline() -> None:
    """Flag on + alert_facility falsy: still emits inline metadata, value="No"."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg"},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        inst = MagicMock()
        inst.originate.return_value = "med_originate"
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "d6a96b19-a087-458a-9619-b46537a8c121"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        inst.Meta.key = "medicationStatement"
        mock_med.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            feature_flags={"AlertFacilityEnabled": True},
        )

    assert len(effects) == 3
    assert json.loads(effects[1].payload)["data"]["value"] == "No"
    assert metadata_pending == []


def test_build_effects_medication_alert_facility_flag_off_no_metadata() -> None:
    """Flag off: no metadata effect emitted, just originate + commit."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg", "alert_facility": True},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        inst = MagicMock()
        inst.originate.return_value = "med_originate"
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "d6a96b19-a087-458a-9619-b46537a8c121"
        inst.note_uuid = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"
        mock_med.return_value = inst

        effects, metadata_pending, attempted, build_errors = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            feature_flags={"AlertFacilityEnabled": False},
        )

    assert len(effects) == 2
    assert effects == ["med_originate", "med_commit"]
    assert metadata_pending == []


_AUTHORIZED_NOTE = "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0"


def test_build_metadata_effects() -> None:
    """Phase 2 builds upsert_metadata effects when the command exists on the
    authorized note."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": _AUTHORIZED_NOTE,
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    stub.upsert_metadata.return_value = "upsert_effect"
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub) as mock_stub,
    ):
        mock_command.objects.filter.return_value.exists.return_value = True
        effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)

    assert effects == ["upsert_effect"]
    assert rejected == 0
    stub.upsert_metadata.assert_called_once_with("alert_facility", "Yes")
    # The per-item visibility check is scoped to BOTH id AND the authorized
    # note_uuid — this is what makes the same retry serve both the race-
    # tolerance concern and the per-item authz concern.
    mock_command.objects.filter.assert_called_with(
        id="d6a96b19-a087-458a-9619-b46537a8c121", note__id=_AUTHORIZED_NOTE
    )
    # build_stub gets the AUTHORIZED note_uuid, not the item's — defense-in-depth.
    mock_stub.assert_called_once_with("d6a96b19-a087-458a-9619-b46537a8c121", _AUTHORIZED_NOTE)


def test_build_metadata_effects_skips_when_command_not_visible() -> None:
    """If the command never shows up in the DB, the upsert is skipped (not raised).
    This is the route that legitimate phase-1-race-delayed commands take when
    Canvas is slow to apply the commit effects."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": _AUTHORIZED_NOTE,
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch("hyperscribe.scribe.commands.builder.time.sleep"),
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub),
    ):
        mock_command.objects.filter.return_value.exists.return_value = False
        effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)

    assert effects == []
    assert rejected == 1
    stub.upsert_metadata.assert_not_called()


def test_build_metadata_effects_retries_through_phase1_race() -> None:
    """The visibility wait retries until the command appears. A legitimate
    command delayed by Canvas's async phase-1 application must NOT be silently
    dropped — it should retry and succeed.

    Regression guard for the round-7 silent-data-loss bug where the API-layer
    authz filter ran a synchronous one-shot query with no retry, collapsing
    `pending` to [] on every race and silently losing alert_facility writes.
    """
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": _AUTHORIZED_NOTE,
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    stub.upsert_metadata.return_value = "upsert_effect"
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch("hyperscribe.scribe.commands.builder.time.sleep"),
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub),
    ):
        # First check returns False (race — Canvas hasn't applied phase-1 yet),
        # second check returns True (Canvas caught up). Item should still be
        # accepted, not silently dropped.
        mock_command.objects.filter.return_value.exists.side_effect = [False, True]
        effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)

    assert effects == ["upsert_effect"]
    assert rejected == 0


def test_build_metadata_effects_rejects_foreign_command_uuid() -> None:
    """Per-item authz: a command_uuid that doesn't belong to the authorized
    note (e.g. a malicious client supplying a foreign uuid) never satisfies
    the scoped visibility filter and is rejected after the retry cap."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "00000000-0000-0000-0000-00000000foreign".replace("foreign", "fffffff"),
            "command_type": "medication_statement",
            "note_uuid": "smuggled-other-note",  # client-supplied; must be ignored
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch("hyperscribe.scribe.commands.builder.time.sleep"),
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub),
    ):
        # The scoped filter (id AND note__id) NEVER returns True because the
        # uuid doesn't belong to the authorized note.
        mock_command.objects.filter.return_value.exists.return_value = False
        effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)

    assert effects == []
    assert rejected == 1
    # Confirm the scoped filter was queried with the AUTHORIZED note_uuid,
    # not the smuggled one — that's what makes this a real security check.
    filter_call = mock_command.objects.filter.call_args
    assert filter_call.kwargs["note__id"] == _AUTHORIZED_NOTE


def test_build_metadata_effects_tolerates_malformed_uuid() -> None:
    """A non-UUID command_uuid string (from a direct API caller) must not
    crash — the broad exception handler in _wait_for_command_in_note treats
    Django's ValidationError as 'not visible' and the retry cap drops it."""
    from django.core.exceptions import ValidationError

    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "not-a-real-uuid",
            "command_type": "medication_statement",
            "note_uuid": _AUTHORIZED_NOTE,
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch("hyperscribe.scribe.commands.builder.time.sleep"),
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub),
    ):
        mock_command.objects.filter.return_value.exists.side_effect = ValidationError(
            "“not-a-real-uuid” is not a valid UUID."
        )
        effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)

    assert effects == []
    assert rejected == 1


def test_build_metadata_effects_swallows_upsert_errors() -> None:
    """If upsert_metadata raises (e.g. SDK validation), other items still process."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": _AUTHORIZED_NOTE,
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    stub.upsert_metadata.side_effect = RuntimeError("simulated SDK validation failure")
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub),
    ):
        mock_command.objects.filter.return_value.exists.return_value = True
        effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)

    assert effects == []
    assert rejected == 1


def test_build_metadata_effects_empty() -> None:
    """Empty pending list returns no effects and zero rejections."""
    effects, rejected = build_metadata_effects([], _AUTHORIZED_NOTE)
    assert effects == []
    assert rejected == 0


def test_build_metadata_effects_unknown_type() -> None:
    """Unknown command type in pending is skipped."""
    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "command_type": "nonexistent_type",
            "note_uuid": _AUTHORIZED_NOTE,
            "metadata": {"key": "val"},
        },
    ]
    effects, rejected = build_metadata_effects(pending, _AUTHORIZED_NOTE)
    assert effects == []
    assert rejected == 1


def test_validate_proposals_all_valid() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "Short text"}, "display": "Migraine"},
        {"command_type": "assess", "data": {"narrative": "Brief"}, "display": "HTN"},
        {"command_type": "prescribe", "data": {"sig": "Take daily"}, "display": "Lisinopril"},
    ]
    assert validate_proposals(proposals) == []


def test_validate_proposals_diagnose_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "x" * 2049}, "display": "Migraine"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert errors[0]["command_type"] == "diagnose"
    assert errors[0]["display"] == "Migraine"
    assert "2048" in errors[0]["errors"][0]


def test_validate_proposals_assess_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "assess", "data": {"narrative": "x" * 2049}, "display": "HTN"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert errors[0]["command_type"] == "assess"


def test_validate_proposals_prescription_sig_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "prescribe", "data": {"sig": "x" * 1001}, "display": "Lisinopril"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert "Sig" in errors[0]["errors"][0]


def test_validate_proposals_prescription_note_to_pharmacist_over_limit() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "prescribe", "data": {"sig": "ok", "note_to_pharmacist": "x" * 1025}, "display": "Lisinopril"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert "pharmacist" in errors[0]["errors"][0].lower()


def test_validate_proposals_multiple_failures() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "x" * 2049}, "display": "Migraine"},
        {"command_type": "prescribe", "data": {"sig": "x" * 1001, "note_to_pharmacist": "x" * 1025}, "display": "Rx"},
        {"command_type": "allergy", "data": {"reaction": "x" * 513}, "display": "Penicillin"},
        {"command_type": "lab_order", "data": {"comment": "x" * 129}, "display": "CBC"},
        {
            "command_type": "imaging_order",
            "data": {"additional_details": "x" * 1025, "comment": "x" * 1025},
            "display": "MRI",
        },
        {"command_type": "stop_medication", "data": {"rationale": "x" * 1025}, "display": "Stop med"},
        {"command_type": "refer", "data": {}, "display": "Cardiology"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 7
    # Prescription has 2 errors (sig + note_to_pharmacist)
    rx_errors = next(e for e in errors if e["command_type"] == "prescribe")
    assert len(rx_errors["errors"]) == 2
    # Imaging has 4 errors (ordering provider + indications + details + comment)
    img_errors = next(e for e in errors if e["command_type"] == "imaging_order")
    assert len(img_errors["errors"]) == 4
    # Refer has 2 errors (notes_to_specialist + indications)
    refer_errors = next(e for e in errors if e["command_type"] == "refer")
    assert len(refer_errors["errors"]) == 2


def test_validate_proposals_unknown_type_skipped() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "unknown", "data": {"text": "x" * 99999}, "display": "???"},
    ]
    assert validate_proposals(proposals) == []


def test_validate_imaging_order_missing_provider_and_indications() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "imaging_order", "data": {"comment": "MRI"}, "display": "MRI Brain"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert len(errors[0]["errors"]) == 2
    error_text = " ".join(errors[0]["errors"])
    assert "Ordering provider" in error_text
    assert "indication" in error_text.lower()


def test_validate_imaging_order_with_required_fields() -> None:
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "imaging_order",
            "data": {"ordering_provider_id": "staff-uuid", "diagnosis_codes": ["J06.9"]},
            "display": "MRI",
        },
    ]
    assert validate_proposals(proposals) == []


def test_validate_refer_missing_notes_and_indications() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "refer", "data": {"service_provider": {"first_name": "Dr"}}, "display": "Cardiology"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert len(errors[0]["errors"]) == 2
    error_text = " ".join(errors[0]["errors"])
    assert "Notes to specialist" in error_text
    assert "indication" in error_text.lower()


def test_validate_refer_with_required_fields() -> None:
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "refer",
            "data": {"notes_to_specialist": "Evaluate murmur", "diagnosis_codes": ["I10"]},
            "display": "Cardiology",
        },
    ]
    assert validate_proposals(proposals) == []


def test_validate_proposals_refill_and_adjust() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "refill", "data": {"sig": "x" * 1001}, "display": "Refill"},
        {"command_type": "adjust_prescription", "data": {"sig": "x" * 1001}, "display": "Adjust"},
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 2


def test_build_effects_vitals_out_of_range_returns_build_error() -> None:
    """Pydantic ValidationError from the SDK is caught and surfaced as a structured per-command error.

    Regression for KOALA-5476: previously, a single out-of-range vital made the entire
    insert-commands batch crash with a generic 500.

    Per UAT feedback on PR #273, the error message must be a concise plain-English
    sentence (no raw input dump, no Pydantic-internal phrasing). The display label
    is set to the friendly command name ("Vitals") so the rendered output reads
    "Vitals: pulse must be greater than or equal to 30 (currently 8)".
    """
    proposals: list[dict[str, Any]] = [
        {"command_type": "vitals", "data": {"pulse": 8}, "display": "HR 8"},
    ]
    effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []
    assert len(build_errors) == 1
    err = build_errors[0]
    assert err["command_type"] == "vitals"
    assert err["display"] == "Vitals"
    assert err["errors"] == ["pulse must be greater than or equal to 30 (currently 8)"]


def test_build_effects_vitals_too_low_message_format() -> None:
    """A too-low vital value renders as ``<field> must be greater than or equal to <min> (currently <value>)``."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_systole": 5},
            "display": "BP 5/?",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert build_errors[0]["display"] == "Vitals"
    assert build_errors[0]["errors"] == [
        "blood_pressure_systole must be greater than or equal to 30 (currently 5)",
    ]


def test_build_effects_vitals_too_high_message_format() -> None:
    """A too-high vital value renders as ``<field> must be less than or equal to <max> (currently <value>)``."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_systole": 999},
            "display": "BP 999/?",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert build_errors[0]["display"] == "Vitals"
    assert build_errors[0]["errors"] == [
        "blood_pressure_systole must be less than or equal to 305 (currently 999)",
    ]


def test_build_effects_vitals_multiple_invalid_fields_each_render_one_line() -> None:
    """When multiple vital fields fail validation, each error renders on its own line.

    Mirrors what the UI does (one ``<li>`` per error). The display label stays "Vitals";
    each error is the field-specific sentence with no raw input dictionary in it.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_systole": 5, "pulse": 8},
            "display": "BP 5/?, HR 8",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    err = build_errors[0]
    assert err["display"] == "Vitals"
    assert set(err["errors"]) == {
        "blood_pressure_systole must be greater than or equal to 30 (currently 5)",
        "pulse must be greater than or equal to 30 (currently 8)",
    }
    # No raw input dictionary or Pydantic-internal phrasing leaks into the message.
    for msg in err["errors"]:
        assert "Input should be" not in msg
        assert "(got " not in msg


def test_build_effects_vitals_string_too_long_does_not_leak_input() -> None:
    """For string-length violations, the message names the field and limit but never includes
    the raw input string (which could carry free-text PHI in the note field)."""
    long_note = "x" * 200
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"pulse": 80, "note": long_note},
            "display": "HR 80, long note",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    err = build_errors[0]
    assert err["display"] == "Vitals"
    assert err["errors"] == ["note must be at most 150 characters"]
    for msg in err["errors"]:
        assert long_note not in msg


def test_build_effects_one_invalid_does_not_block_others() -> None:
    """A bad vitals proposal does not prevent other commands from being originated."""
    proposals: list[dict[str, Any]] = [
        {"command_type": "vitals", "data": {"pulse": 8}, "display": "HR 8"},
        {"command_type": "rfv", "data": {"comment": "Headache"}, "display": "Headache"},
    ]
    with patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv:
        inst = MagicMock()
        inst.originate.return_value = "rfv_originate"
        inst.commit.return_value = "rfv_commit"
        inst.command_uuid = "rfv-uuid"
        mock_rfv.return_value = inst
        effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == ["rfv_originate", "rfv_commit"]
    assert len(attempted) == 1
    assert attempted[0]["command_type"] == "rfv"
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"


def test_build_effects_vitals_invalid_enum_returns_build_error() -> None:
    """ValueError raised by enum coercion in build() is also caught and surfaced.

    The display label uses the friendly command name ("Vitals"), matching the
    ValidationError branch — the LLM-supplied ``display`` field is untrusted
    free text and must not leak into the response payload.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_position_and_site": 999},
            "display": "BP bad site",
        },
    ]
    effects, metadata_pending, attempted, build_errors = build_effects(proposals, "note-uuid")
    assert effects == []
    assert attempted == []
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"
    assert build_errors[0]["display"] == "Vitals"


def test_build_effects_vitals_int_type_does_not_leak_input() -> None:
    """A non-numeric pulse hits the ``else:`` fallback in ``_format_pydantic_errors``.

    The fallback path historically echoed ``input_value`` verbatim into the rendered
    message, which would leak any LLM-supplied free text (potentially PHI) into both
    the HTTP response and the persisted ``VALIDATION_FAILED`` audit log.

    The PHI marker MUST NOT appear anywhere in the rendered error string.
    """
    phi_marker = "PHI_PLACEHOLDER_xyz"
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"pulse": phi_marker},
            "display": "HR free text",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"
    assert build_errors[0]["display"] == "Vitals"
    rendered = " ".join(build_errors[0]["errors"])
    assert phi_marker not in rendered, f"PHI marker leaked into error message: {rendered!r}"


def test_build_effects_vitals_enum_value_error_does_not_leak_input() -> None:
    """An invalid ``blood_pressure_position_and_site`` raises ``ValueError`` from enum
    coercion in ``VitalsParser.build`` (the parser's ``validate`` does not guard the
    enum domain, see commands/base.py:44). The legacy implementation used
    ``str(exc)`` in the ``except ValueError`` branch, which echoes the raw input
    value verbatim into the message.

    Critical leak sink: ``session_view.py`` writes ``build_errors`` to
    ``audit_event("VALIDATION_FAILED", source="build")``, so any echoed PHI is
    persisted to audit logs — a direct HIPAA violation.

    The PHI marker MUST NOT appear anywhere in the rendered error string.
    """
    phi_marker = "PHI_PLACEHOLDER_abc"
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_position_and_site": phi_marker},
            "display": "BP free text",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert len(build_errors) == 1
    assert build_errors[0]["command_type"] == "vitals"
    assert build_errors[0]["display"] == "Vitals"
    rendered = " ".join(build_errors[0]["errors"])
    assert phi_marker not in rendered, f"PHI marker leaked into error message: {rendered!r}"


def test_value_error_branch_message_preserves_field_name() -> None:
    """The ``except ValueError`` branch must surface the failing field name (``loc``)
    so the clinician knows *which* field is wrong and can re-prompt / correct it.

    Paired contract with ``test_build_effects_vitals_enum_value_error_does_not_leak_input``:
    that test guards against echoing the *raw input* (PHI leak); this test guards against
    over-sanitizing into a generic message that loses the field name (a UX regression).
    Together they pin both directions: field name in, raw input out.

    The field name is developer-defined (``blood_pressure_position_and_site``), not
    user/LLM input, so PHI-safe. See the loc-invariant comment in builder.py.
    """
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "vitals",
            "data": {"blood_pressure_position_and_site": "sitting-and-on-the-left-wrist"},
            "display": "BP bad site",
        },
    ]
    _, _, _, build_errors = build_effects(proposals, "note-uuid")
    assert len(build_errors) == 1
    rendered = " ".join(build_errors[0]["errors"])
    assert "blood_pressure_position_and_site" in rendered, (
        f"Field name missing from rendered ValueError-branch message: {rendered!r}. "
        "Clinician must see which field is wrong; a generic 'invalid value' is unactionable."
    )


# Pydantic v2 type-string contract: each row is (type_string, model_factory, bad_input,
# friendly_substring). The point of this parametrized test is to catch the day Pydantic
# renames any of these type strings — the current implementation matches them by string
# in an if/elif chain, and a silent rename would degrade every match into the ``else:``
# fallback (PHI-leak branch). This test fails loudly instead.
@pytest.mark.parametrize(
    ("type_string", "model_factory", "bad_input", "friendly_substring"),
    [
        (
            "greater_than_equal",
            lambda: _make_constrained_int_model(ge=10),
            5,
            "greater than or equal to 10",
        ),
        (
            "less_than_equal",
            lambda: _make_constrained_int_model(le=100),
            200,
            "less than or equal to 100",
        ),
        (
            "greater_than",
            lambda: _make_constrained_int_model(gt=0),
            -1,
            "greater than 0",
        ),
        (
            "less_than",
            lambda: _make_constrained_int_model(lt=100),
            200,
            "less than 100",
        ),
        (
            "string_too_long",
            lambda: _make_constrained_str_model(max_length=5),
            "x" * 10,
            "at most 5 characters",
        ),
        (
            "string_too_short",
            lambda: _make_constrained_str_model(min_length=5),
            "ab",
            "at least 5 characters",
        ),
        (
            "missing",
            lambda: _make_required_field_model(),
            None,  # sentinel - factory triggers a missing-field error itself
            "is required",
        ),
    ],
)
def test_format_pydantic_errors_recognized_type_strings_take_friendly_path(
    type_string: str,
    model_factory: Any,
    bad_input: Any,
    friendly_substring: str,
) -> None:
    """Each Pydantic v2 type string in the if/elif chain must produce its friendly
    rendering — never the ``else:`` fallback (which is the PHI-leak branch).

    Mechanism: construct a real Pydantic v2 BaseModel with the matching constraint,
    instantiate with bad input, catch the real ValidationError, run it through
    ``_format_pydantic_errors``, then assert (a) the resulting message contains the
    friendly substring and (b) the canonical "Input should be" / "(got " Pydantic
    phrasing is absent — which is how the fallback branch renders.
    """
    model = model_factory()
    try:
        if type_string == "missing":
            model()  # type: ignore[call-arg]
        else:
            model(value=bad_input)
    except ValidationError as exc:
        # First confirm Pydantic still emits this exact type string. If this assertion
        # fails, Pydantic renamed the type and the if/elif chain in builder.py is now
        # silently degrading into the fallback.
        emitted_types = [err.get("type") for err in exc.errors()]
        assert type_string in emitted_types, (
            f"Pydantic emitted {emitted_types!r}, expected {type_string!r}. "
            "The if/elif chain in _format_pydantic_errors will now fall through "
            "to the PHI-leak fallback for this constraint."
        )
        messages = _format_pydantic_errors(exc)
    else:
        raise AssertionError("Expected ValidationError but none was raised")

    rendered = " ".join(messages)
    assert friendly_substring in rendered, (
        f"Friendly substring {friendly_substring!r} missing from rendered "
        f"messages {messages!r} - likely fell through to the fallback branch."
    )
    # The fallback formats as "<loc>: <msg> (currently <input>)" where <msg> is
    # Pydantic's "Input should be ..." phrasing. None of those markers should appear.
    assert "Input should be" not in rendered
    assert "(got " not in rendered
