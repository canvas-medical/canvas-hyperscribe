from typing import Any
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.builder import build_effects, build_metadata_effects


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
        patch("hyperscribe.scribe.commands.builder.BatchOriginateCommandEffect") as mock_batch,
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
            inst.originate.return_value = f"{mock._mock_name}_effect"
            inst.commit.return_value = f"{mock._mock_name}_commit"
            inst.review.return_value = f"{mock._mock_name}_review"
            inst.command_uuid = "test-uuid"
            inst.note_uuid = "note-uuid"
            mock.return_value = inst

        mock_batch_inst = MagicMock()
        mock_batch_inst.apply.return_value = "batch_effect"
        mock_batch.return_value = mock_batch_inst

        effects, metadata_pending = build_effects(proposals, "note-uuid")

    # 1 batch (12 non-custom) + 2 individual originate (history, chart) + 13 commits + 1 review
    assert len(effects) == 17
    assert effects[0] == "batch_effect"
    assert metadata_pending == []
    mock_rfv.assert_called_once()
    mock_hpi.assert_called_once()
    mock_vitals.assert_called_once()
    mock_plan.assert_called_once()
    mock_med.assert_called_once()
    mock_task.assert_called_once()
    mock_rx.assert_called_once()
    mock_lab.assert_called_once()
    mock_img.assert_called_once()
    mock_history.assert_called_once()
    mock_chart.assert_called_once()
    mock_allergy.assert_called_once()
    mock_diagnose.assert_called_once()
    mock_assess.assert_called_once()


def test_build_effects_unknown_type_skipped() -> None:
    proposals: list[dict[str, Any]] = [{"command_type": "unknown_type", "data": {"foo": "bar"}}]
    effects, metadata_pending = build_effects(proposals, "note-uuid")
    assert effects == []
    assert metadata_pending == []


def test_build_effects_empty_list() -> None:
    effects, metadata_pending = build_effects([], "note-uuid")
    assert effects == []
    assert metadata_pending == []


def test_build_effects_medication_with_alert_facility() -> None:
    """Medication statement with alert_facility produces metadata_pending."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg", "alert_facility": True},
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med,
        patch("hyperscribe.scribe.commands.builder.BatchOriginateCommandEffect") as mock_batch,
    ):
        inst = MagicMock()
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "cmd-uuid-123"
        inst.note_uuid = "note-uuid"
        mock_med.return_value = inst
        mock_batch_inst = MagicMock()
        mock_batch_inst.apply.return_value = "batch_effect"
        mock_batch.return_value = mock_batch_inst

        effects, metadata_pending = build_effects(proposals, "note-uuid")

    assert len(effects) == 2  # 1 batch + 1 commit
    assert effects[0] == "batch_effect"
    assert len(metadata_pending) == 1
    assert metadata_pending[0]["command_uuid"] == "cmd-uuid-123"
    assert metadata_pending[0]["command_type"] == "medication_statement"
    assert metadata_pending[0]["metadata"] == {"alert_facility": "true"}


def test_build_effects_medication_without_alert_facility() -> None:
    """Medication statement without alert_facility produces no metadata_pending."""
    proposals: list[dict[str, Any]] = [
        {
            "command_type": "medication_statement",
            "data": {"medication_text": "Lisinopril 10mg"},
        },
    ]
    with (
        patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med,
        patch("hyperscribe.scribe.commands.builder.BatchOriginateCommandEffect") as mock_batch,
    ):
        inst = MagicMock()
        inst.commit.return_value = "med_commit"
        inst.command_uuid = "cmd-uuid-123"
        inst.note_uuid = "note-uuid"
        mock_med.return_value = inst
        mock_batch_inst = MagicMock()
        mock_batch_inst.apply.return_value = "batch_effect"
        mock_batch.return_value = mock_batch_inst

        effects, metadata_pending = build_effects(proposals, "note-uuid")

    assert len(effects) == 2  # 1 batch + 1 commit
    assert metadata_pending == []


def test_build_metadata_effects() -> None:
    """Phase 2 builds upsert_metadata effects from pending items."""
    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "cmd-uuid-123",
            "command_type": "medication_statement",
            "note_uuid": "note-uuid",
            "metadata": {"alert_facility": "true"},
        },
    ]
    with patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med:
        stub = MagicMock()
        stub.upsert_metadata.return_value = "upsert_effect"
        mock_med.return_value = stub

        effects = build_metadata_effects(pending)

    assert len(effects) == 1
    assert effects[0] == "upsert_effect"
    stub.upsert_metadata.assert_called_once_with("alert_facility", "true")
    mock_med.assert_called_once_with(command_uuid="cmd-uuid-123", note_uuid="note-uuid")


def test_build_metadata_effects_empty() -> None:
    """Empty pending list returns no effects."""
    effects = build_metadata_effects([])
    assert effects == []


def test_build_metadata_effects_unknown_type() -> None:
    """Unknown command type in pending is skipped."""
    pending: list[dict[str, Any]] = [
        {
            "command_uuid": "cmd-uuid",
            "command_type": "nonexistent_type",
            "note_uuid": "note-uuid",
            "metadata": {"key": "val"},
        },
    ]
    effects = build_metadata_effects(pending)
    assert effects == []
