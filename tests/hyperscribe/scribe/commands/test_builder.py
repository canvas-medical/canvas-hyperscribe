import json
from typing import Any
from unittest.mock import MagicMock, patch

from canvas_generated.messages.effects_pb2 import EffectType

from hyperscribe.scribe.commands.builder import build_effects, build_metadata_effects, validate_proposals


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

        effects, metadata_pending, attempted = build_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

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
    effects, metadata_pending, attempted = build_effects(proposals, "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []


def test_build_effects_empty_list() -> None:
    effects, metadata_pending, attempted = build_effects([], "note-uuid")
    assert effects == []
    assert metadata_pending == []
    assert attempted == []


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

        effects, metadata_pending, attempted = build_effects(
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

        effects, metadata_pending, attempted = build_effects(
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

        effects, metadata_pending, attempted = build_effects(
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
