from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.perform import PerformParser


def test_extract_returns_none() -> None:
    parser = PerformParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = PerformParser()
    assert parser.extract_all("some text") == []


def test_build_with_cpt_code() -> None:
    parser = PerformParser()
    data = {"cpt_code": "99213", "notes": "Follow-up visit"}
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid-456")

    mock_cmd.assert_called_once_with(
        cpt_code="99213",
        notes="Follow-up visit",
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid-456",
    )


def test_build_without_cpt_code() -> None:
    parser = PerformParser()
    data = {"cpt_code": None, "notes": None}
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        cpt_code=None,
        notes=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_empty_strings_becomes_none() -> None:
    parser = PerformParser()
    data = {"cpt_code": "", "notes": ""}
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        cpt_code=None,
        notes=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_missing_fields() -> None:
    parser = PerformParser()
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        cpt_code=None,
        notes=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_notes() -> None:
    parser = PerformParser()
    data = {"cpt_code": "99342", "notes": "Home visit new patient, moderate complexity"}
    with patch("hyperscribe.scribe.commands.perform.PerformCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        cpt_code="99342",
        notes="Home visit new patient, moderate complexity",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    parser = PerformParser()
    assert parser.command_type == "perform"


def test_data_field_is_none() -> None:
    parser = PerformParser()
    assert parser.data_field is None
