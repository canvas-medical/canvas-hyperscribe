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
