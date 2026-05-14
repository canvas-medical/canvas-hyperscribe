from typing import Any
from unittest.mock import MagicMock, patch

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


def test_build_effects_medication_with_alert_facility() -> None:
    """Medication statement with alert_facility produces metadata_pending."""
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

        effects, metadata_pending, attempted = build_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert len(effects) == 2  # 1 originate + 1 commit
    assert effects[0] == "med_originate"
    assert len(metadata_pending) == 1
    assert metadata_pending[0]["command_uuid"] == "d6a96b19-a087-458a-9619-b46537a8c121"
    assert metadata_pending[0]["command_type"] == "medication_statement"
    assert metadata_pending[0]["metadata"] == {"alert_facility": "true"}
    assert len(attempted) == 1
    assert attempted[0]["command_type"] == "medication_statement"


def test_build_effects_medication_without_alert_facility() -> None:
    """Medication statement without alert_facility produces no metadata_pending."""
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
        mock_med.return_value = inst

        effects, metadata_pending, attempted = build_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert len(effects) == 2  # 1 originate + 1 commit
    assert metadata_pending == []


def test_build_metadata_effects() -> None:
    """Phase 2 builds upsert_metadata effects from pending items."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            "metadata": {"alert_facility": "true"},
        },
    ]
    stub = MagicMock()
    stub.upsert_metadata.return_value = "upsert_effect"
    with patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub):
        effects = build_metadata_effects(pending)

    assert len(effects) == 1
    assert effects[0] == "upsert_effect"
    stub.upsert_metadata.assert_called_once_with("alert_facility", "true")


def test_build_metadata_effects_empty() -> None:
    """Empty pending list returns no effects."""
    effects = build_metadata_effects([])
    assert effects == []


def test_build_metadata_effects_unknown_type() -> None:
    """Unknown command type in pending is skipped."""
    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
            "command_type": "nonexistent_type",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            "metadata": {"key": "val"},
        },
    ]
    effects = build_metadata_effects(pending)
    assert effects == []


_GOOD_RX_DATA = {
    "fdb_code": "285665",
    "sig": "Take 1 tablet by mouth daily",
    "quantity_to_dispense": 30,
    "type_to_dispense": "C48480",
    "refills": 2,
    "substitutions": "allowed",
}


def test_validate_proposals_all_valid() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "Short text"}, "display": "Migraine"},
        {"command_type": "assess", "data": {"narrative": "Brief"}, "display": "HTN"},
        # Prescribe / Refill / Adjust Prescription all share canvas-core's
        # Prescribe schema and need every required field populated to pass.
        {"command_type": "prescribe", "data": dict(_GOOD_RX_DATA), "display": "Lisinopril"},
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
        {
            "command_type": "prescribe",
            "data": {**_GOOD_RX_DATA, "sig": "x" * 1001},
            "display": "Lisinopril",
        },
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert any("Sig" in e for e in errors[0]["errors"])


def test_validate_proposals_prescription_note_to_pharmacist_over_limit() -> None:
    """Regression: limit is 210 (Surescripts NewRx), not 1024."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "prescribe",
            "data": {**_GOOD_RX_DATA, "note_to_pharmacist": "x" * 211},
            "display": "Lisinopril",
        },
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert any("pharmacist" in e.lower() for e in errors[0]["errors"])


def test_validate_proposals_multiple_failures() -> None:
    proposals: list[dict[str, Any]] = [
        {"command_type": "diagnose", "data": {"today_assessment": "x" * 2049}, "display": "Migraine"},
        # Send a prescribe with both sig over-limit AND note_to_pharmacist
        # over the 210-char Surescripts cap. Other required fields are
        # populated so we isolate the assertions to the over-limit checks.
        {
            "command_type": "prescribe",
            "data": {**_GOOD_RX_DATA, "sig": "x" * 1001, "note_to_pharmacist": "x" * 211},
            "display": "Rx",
        },
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
    # Prescription has 2 errors (sig over-limit + note_to_pharmacist over-limit)
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
        {
            "command_type": "refill",
            "data": {**_GOOD_RX_DATA, "sig": "x" * 1001},
            "display": "Refill",
        },
        {
            "command_type": "adjust_prescription",
            "data": {**_GOOD_RX_DATA, "sig": "x" * 1001},
            "display": "Adjust",
        },
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 2


def test_validate_proposals_adjust_prescription_missing_refills() -> None:
    """Regression for the failure on Brigade note 20746: refills was None,
    the originate succeeded, and REVIEW raised the generic
    ValidationError("Command cannot be reviewed due to incomplete data...")
    after /insert-commands had already returned 200."""
    incomplete = {**_GOOD_RX_DATA, "refills": None}
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "adjust_prescription",
            "data": incomplete,
            "display": "Lisinopril",
        },
    ]
    errors = validate_proposals(proposals)
    assert len(errors) == 1
    assert any("Refills is required" in e for e in errors[0]["errors"])


def test_validate_proposals_runs_chart_state_check_when_note_uuid_present() -> None:
    """When note_uuid is supplied, refill / adjust_prescription parsers also
    verify the source medication is active on the patient. Skipping that
    validation by omitting note_uuid keeps unit tests DB-free."""
    from unittest.mock import patch

    proposals: list[dict[str, Any]] = [
        {"command_type": "refill", "data": dict(_GOOD_RX_DATA), "display": "Refill"},
    ]
    # Without note_uuid, no DB call.
    assert validate_proposals(proposals) == []

    # With note_uuid, the parser checks the chart and surfaces an error if
    # the medication is not active for this patient.
    with (
        patch("hyperscribe.scribe.commands.refill.Note") as mock_note,
        patch("hyperscribe.scribe.commands.refill.Medication") as mock_med,
    ):
        mock_note.objects.values_list.return_value.get.return_value = "patient-1"
        mock_med.objects.filter.return_value.exists.return_value = False
        errors = validate_proposals(proposals, note_uuid="note-uuid")

    assert len(errors) == 1
    assert any("not active on this patient" in e for e in errors[0]["errors"])


def test_validate_proposals_logs_when_chart_validator_raises(caplog: Any) -> None:
    """Unexpected exceptions from ``validate_against_patient`` fail open (so
    transient DB issues don't block writes) but MUST log so schema drift or
    programming errors are diagnosable from the audit log."""
    import logging
    from unittest.mock import patch

    proposals: list[dict[str, Any]] = [
        {"command_type": "refill", "data": dict(_GOOD_RX_DATA), "display": "Refill"},
    ]

    with (
        patch(
            "hyperscribe.scribe.commands.refill.RefillParser.validate_against_patient",
            side_effect=RuntimeError("simulated schema drift"),
        ),
        caplog.at_level(logging.ERROR, logger="hyperscribe.scribe.commands.builder"),
    ):
        errors = validate_proposals(proposals, note_uuid="note-uuid")

    # Fail open — no errors raised to caller.
    assert errors == []
    # But the failure is captured in the log for diagnosis.
    assert any("chart_validator raised" in rec.message for rec in caplog.records)
    assert any("simulated schema drift" in (rec.exc_text or "") for rec in caplog.records)
