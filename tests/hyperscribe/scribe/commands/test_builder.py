from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.builder import build_effects


def test_build_effects_routes_all_types() -> None:
    proposals = [
        {"command_type": "rfv", "data": {"comment": "Headache"}},
        {"command_type": "hpi", "data": {"narrative": "Two weeks of headaches"}},
        {"command_type": "vitals", "data": {"pulse": 72, "blood_pressure_systole": 120, "blood_pressure_diastole": 80}},
        {"command_type": "plan", "data": {"narrative": "Start sumatriptan"}},
        {"command_type": "medication_statement", "data": {"medication_text": "Lisinopril 10mg"}},
    ]
    with (
        patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_rfv,
        patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.plan.PlanCommand") as mock_plan,
        patch("hyperscribe.scribe.commands.vitals.VitalsCommand") as mock_vitals,
        patch("hyperscribe.scribe.commands.medication_statement.MedicationStatementCommand") as mock_med,
    ):
        for mock in [mock_rfv, mock_hpi, mock_plan, mock_vitals, mock_med]:
            inst = MagicMock()
            inst.originate.return_value = f"{mock._mock_name}_effect"
            mock.return_value = inst

        effects = build_effects(proposals, "note-uuid")

    assert len(effects) == 5
    mock_rfv.assert_called_once()
    mock_hpi.assert_called_once()
    mock_vitals.assert_called_once()
    mock_plan.assert_called_once()
    mock_med.assert_called_once()


def test_build_effects_unknown_type_skipped() -> None:
    proposals = [{"command_type": "unknown_type", "data": {"foo": "bar"}}]
    effects = build_effects(proposals, "note-uuid")
    assert effects == []


def test_build_effects_empty_list() -> None:
    effects = build_effects([], "note-uuid")
    assert effects == []
