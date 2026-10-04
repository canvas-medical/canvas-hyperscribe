from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.remove_allergy import RemoveAllergyParser


def test_extract_returns_none() -> None:
    parser = RemoveAllergyParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = RemoveAllergyParser()
    assert parser.extract_all("some text") == []


def test_build_with_all_fields() -> None:
    parser = RemoveAllergyParser()
    data = {"allergy_id": "allergy-uuid-123", "narrative": "Patient tolerated without reaction"}
    with patch("hyperscribe.scribe.commands.remove_allergy.RemoveAllergyCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy_id="allergy-uuid-123",
        narrative="Patient tolerated without reaction",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_missing_fields() -> None:
    parser = RemoveAllergyParser()
    with patch("hyperscribe.scribe.commands.remove_allergy.RemoveAllergyCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy_id=None,
        narrative=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    assert RemoveAllergyParser().command_type == "remove_allergy"


def test_data_field_is_none() -> None:
    assert RemoveAllergyParser().data_field is None
