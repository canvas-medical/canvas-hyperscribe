from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.resolve_condition import ResolveConditionParser


def test_extract_returns_none() -> None:
    parser = ResolveConditionParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = ResolveConditionParser()
    assert parser.extract_all("some text") == []


def test_build_with_all_fields() -> None:
    parser = ResolveConditionParser()
    data = {"condition_id": "cond-uuid-123", "rationale": "Resolved after treatment"}
    with patch("hyperscribe.scribe.commands.resolve_condition.ResolveConditionCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        condition_id="cond-uuid-123",
        rationale="Resolved after treatment",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_missing_fields() -> None:
    parser = ResolveConditionParser()
    with patch("hyperscribe.scribe.commands.resolve_condition.ResolveConditionCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        condition_id=None,
        rationale=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    assert ResolveConditionParser().command_type == "resolve_condition"


def test_data_field_is_none() -> None:
    assert ResolveConditionParser().data_field is None
