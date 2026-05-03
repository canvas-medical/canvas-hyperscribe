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
    """Medication statement with alert_facility=True writes Yes to metadata_pending."""
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
            {"AlertFacilityEnabled": True},
        )

    assert len(effects) == 2  # 1 originate + 1 commit
    assert effects[0] == "med_originate"
    assert len(metadata_pending) == 1
    assert metadata_pending[0]["command_uuid"] == "d6a96b19-a087-458a-9619-b46537a8c121"
    assert metadata_pending[0]["command_type"] == "medication_statement"
    assert metadata_pending[0]["metadata"] == {"alert_facility": "Yes"}
    assert len(attempted) == 1
    assert attempted[0]["command_type"] == "medication_statement"


def test_build_effects_medication_alert_facility_false_writes_no() -> None:
    """When the feature is on, an unset/false alert_facility is persisted as 'No'."""
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

        effects, metadata_pending, attempted = build_effects(
            proposals,
            "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            {"AlertFacilityEnabled": True},
        )

    assert len(effects) == 2
    assert len(metadata_pending) == 1
    assert metadata_pending[0]["metadata"] == {"alert_facility": "No"}


def test_build_effects_medication_alert_facility_disabled() -> None:
    """When the feature flag is off, no alert_facility metadata is emitted."""
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

        # No feature_flags arg → defaults to disabled.
        effects, metadata_pending, attempted = build_effects(proposals, "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0")

    assert len(effects) == 2
    assert metadata_pending == []


def test_build_metadata_effects() -> None:
    """Phase 2 builds upsert_metadata effects from pending items."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
            "metadata": {"alert_facility": "Yes"},
        },
    ]
    stub = MagicMock()
    stub.upsert_metadata.return_value = "upsert_effect"
    with (
        patch("hyperscribe.scribe.commands.builder.Command") as mock_command,
        patch.object(_BUILDERS["medication_statement"], "build_stub", return_value=stub),
    ):
        mock_command.objects.filter.return_value.exists.return_value = True
        effects = build_metadata_effects(pending)

    assert len(effects) == 1
    assert effects[0] == "upsert_effect"
    stub.upsert_metadata.assert_called_once_with("alert_facility", "Yes")


def test_build_metadata_effects_skips_when_command_not_visible() -> None:
    """If the command never shows up in the DB, the upsert is skipped (not raised)."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
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
        effects = build_metadata_effects(pending)

    assert effects == []
    stub.upsert_metadata.assert_not_called()


def test_build_metadata_effects_swallows_upsert_errors() -> None:
    """If upsert_metadata raises (e.g. SDK validation), other items still process."""
    from hyperscribe.scribe.commands.builder import _BUILDERS

    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "d6a96b19-a087-458a-9619-b46537a8c121",
            "command_type": "medication_statement",
            "note_uuid": "5899e7bf-5ecb-4399-aceb-0e233bd4a8f0",
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
        effects = build_metadata_effects(pending)

    assert effects == []


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
