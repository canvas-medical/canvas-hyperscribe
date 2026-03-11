from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.builder import build_effects


def test_build_effects_routes_all_types() -> None:
    proposals = [
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
        ]
        for mock in all_mocks:
            inst = MagicMock()
            inst.originate.return_value = f"{mock._mock_name}_effect"
            mock.return_value = inst

        effects = build_effects(proposals, "note-uuid")

    assert len(effects) == 24
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


def test_build_effects_unknown_type_skipped() -> None:
    proposals = [{"command_type": "unknown_type", "data": {"foo": "bar"}}]
    effects = build_effects(proposals, "note-uuid")
    assert effects == []


def test_build_effects_empty_list() -> None:
    effects = build_effects([], "note-uuid")
    assert effects == []
