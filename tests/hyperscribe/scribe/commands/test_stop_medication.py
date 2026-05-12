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


def _make_stop_command() -> MagicMock:
    cmd = MagicMock()
    cmd.command_uuid = "00000000-0000-0000-0000-0000000000b1"
    cmd.note_uuid = "00000000-0000-0000-0000-0000000000bb"
    return cmd


def test_pending_metadata_flag_off_returns_none() -> None:
    cmd = _make_stop_command()
    proposal = {"data": {"alert_facility": True}}
    assert StopMedicationParser().pending_metadata(cmd, proposal, feature_flags={}) is None
    assert StopMedicationParser().pending_metadata(cmd, proposal, feature_flags=None) is None
    assert (
        StopMedicationParser().pending_metadata(cmd, proposal, feature_flags={"AlertFacilityEnabled": False})
        is None
    )


def test_pending_metadata_flag_on_alert_truthy_returns_yes() -> None:
    cmd = _make_stop_command()
    proposal = {"data": {"alert_facility": True}}
    result = StopMedicationParser().pending_metadata(
        cmd, proposal, feature_flags={"AlertFacilityEnabled": True}
    )
    assert result == {
        "command_uuid": cmd.command_uuid,
        "command_type": "stop_medication",
        "note_uuid": cmd.note_uuid,
        "metadata": {"alert_facility": "Yes"},
    }


def test_pending_metadata_flag_on_alert_falsy_defaults_to_no() -> None:
    cmd = _make_stop_command()
    for proposal in (
        {"data": {"alert_facility": False}},
        {"data": {}},
        None,
    ):
        result = StopMedicationParser().pending_metadata(
            cmd, proposal, feature_flags={"AlertFacilityEnabled": True}
        )
        assert result is not None
        assert result["metadata"] == {"alert_facility": "No"}
