from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.change_medication import ChangeMedicationParser


def test_extract_returns_none() -> None:
    parser = ChangeMedicationParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = ChangeMedicationParser()
    assert parser.extract_all("some text") == []


def test_build() -> None:
    parser = ChangeMedicationParser()
    data = {"medication_id": "med-uuid-123", "sig": "Take 1 tablet daily"}
    with patch("hyperscribe.scribe.commands.change_medication.ChangeMedicationCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        medication_id="med-uuid-123",
        sig="Take 1 tablet daily",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_minimal() -> None:
    parser = ChangeMedicationParser()
    data = {"medication_id": "med-uuid-456"}
    with patch("hyperscribe.scribe.commands.change_medication.ChangeMedicationCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        medication_id="med-uuid-456",
        sig=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_missing_fields() -> None:
    parser = ChangeMedicationParser()
    with patch("hyperscribe.scribe.commands.change_medication.ChangeMedicationCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        medication_id=None,
        sig=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    assert ChangeMedicationParser().command_type == "change_medication"


def test_data_field_is_none() -> None:
    assert ChangeMedicationParser().data_field is None
