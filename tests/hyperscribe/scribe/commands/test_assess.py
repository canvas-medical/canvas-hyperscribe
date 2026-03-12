from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.assess import AssessParser, _parse_status


def test_extract_returns_none() -> None:
    parser = AssessParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = AssessParser()
    assert parser.extract_all("some text") == []


def test_build_with_all_fields() -> None:
    parser = AssessParser()
    data = {
        "condition_id": "cond-uuid-789",
        "narrative": "Stable, continue current medications",
        "background": "Diagnosed 2020",
        "status": "stable",
    }
    with patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        mock_cmd.Status = _get_status_enum()
        parser.build(data, "note-uuid-123", "cmd-uuid-456")

    mock_cmd.assert_called_once_with(
        condition_id="cond-uuid-789",
        narrative="Stable, continue current medications",
        background="Diagnosed 2020",
        status=mock_cmd.Status.STABLE,
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid-456",
    )


def test_build_with_missing_fields_defaults() -> None:
    parser = AssessParser()
    with patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        mock_cmd.Status = _get_status_enum()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        condition_id="",
        narrative="",
        background="",
        status=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_none_values_defaults() -> None:
    parser = AssessParser()
    data = {
        "condition_id": None,
        "narrative": None,
        "background": None,
        "status": None,
    }
    with patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        mock_cmd.Status = _get_status_enum()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        condition_id="",
        narrative="",
        background="",
        status=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_invalid_status_defaults_to_none() -> None:
    parser = AssessParser()
    data = {
        "condition_id": "cond-uuid",
        "narrative": "Assessment text",
        "status": "invalid_status",
    }
    with patch("hyperscribe.scribe.commands.assess.AssessCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        mock_cmd.Status = _get_status_enum()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        condition_id="cond-uuid",
        narrative="Assessment text",
        background="",
        status=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    parser = AssessParser()
    assert parser.command_type == "assess"


def test_data_field_is_none() -> None:
    parser = AssessParser()
    assert parser.data_field is None


def test_parse_status_valid() -> None:
    from canvas_sdk.commands.commands.assess import AssessCommand

    assert _parse_status("stable") == AssessCommand.Status.STABLE
    assert _parse_status("improved") == AssessCommand.Status.IMPROVED
    assert _parse_status("deteriorated") == AssessCommand.Status.DETERIORATED


def test_parse_status_invalid() -> None:
    assert _parse_status("unknown") is None
    assert _parse_status(None) is None
    assert _parse_status("") is None


def _get_status_enum() -> type:
    """Create a real-like Status enum for mocked AssessCommand."""
    from canvas_sdk.commands.commands.assess import AssessCommand

    return AssessCommand.Status
