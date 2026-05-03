from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.stop_medication import StopMedicationParser


def test_extract_returns_none() -> None:
    parser = StopMedicationParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = StopMedicationParser()
    assert parser.extract_all("some text") == []


def test_build_with_all_fields() -> None:
    parser = StopMedicationParser()
    data = {"medication_id": "med-uuid-123", "rationale": "No longer needed"}
    with patch("hyperscribe.scribe.commands.stop_medication.StopMedicationCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        medication_id="med-uuid-123",
        rationale="No longer needed",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_missing_fields() -> None:
    parser = StopMedicationParser()
    with patch("hyperscribe.scribe.commands.stop_medication.StopMedicationCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        medication_id=None,
        rationale=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    assert StopMedicationParser().command_type == "stop_medication"


def test_data_field_is_none() -> None:
    assert StopMedicationParser().data_field is None


def _make_command_stub() -> MagicMock:
    cmd = MagicMock()
    cmd.command_uuid = "cmd-uuid"
    cmd.note_uuid = "note-uuid"
    return cmd


def test_pending_metadata_yes_when_flag_on_and_alert_true() -> None:
    parser = StopMedicationParser()
    proposal = {"data": {"medication_id": "m1", "alert_facility": True}}
    result = parser.pending_metadata(_make_command_stub(), proposal, {"AlertFacilityEnabled": True})
    assert result == {
        "command_uuid": "cmd-uuid",
        "command_type": "stop_medication",
        "note_uuid": "note-uuid",
        "metadata": {"alert_facility": "Yes"},
    }


def test_pending_metadata_no_when_flag_on_and_alert_false() -> None:
    parser = StopMedicationParser()
    proposal = {"data": {"medication_id": "m1", "alert_facility": False}}
    result = parser.pending_metadata(_make_command_stub(), proposal, {"AlertFacilityEnabled": True})
    assert result is not None
    assert result["metadata"] == {"alert_facility": "No"}


def test_pending_metadata_no_when_flag_on_and_alert_missing() -> None:
    parser = StopMedicationParser()
    proposal = {"data": {"medication_id": "m1"}}
    result = parser.pending_metadata(_make_command_stub(), proposal, {"AlertFacilityEnabled": True})
    assert result is not None
    assert result["metadata"] == {"alert_facility": "No"}


def test_pending_metadata_none_when_flag_off() -> None:
    parser = StopMedicationParser()
    proposal = {"data": {"medication_id": "m1", "alert_facility": True}}
    assert parser.pending_metadata(_make_command_stub(), proposal, {"AlertFacilityEnabled": False}) is None
    assert parser.pending_metadata(_make_command_stub(), proposal, None) is None
    assert parser.pending_metadata(_make_command_stub(), proposal) is None
