from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.diagnose import DiagnoseParser


def test_extract_returns_none() -> None:
    parser = DiagnoseParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = DiagnoseParser()
    assert parser.extract_all("some text") == []


def test_build_with_all_fields() -> None:
    parser = DiagnoseParser()
    data = {
        "icd10_code": "G43.009",
        "today_assessment": "Migraine without aura, start sumatriptan",
        "background": "History of migraines since 2018",
    }
    with patch("hyperscribe.scribe.commands.diagnose.DiagnoseCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-123", "cmd-uuid-456")

    mock_cmd.assert_called_once_with(
        icd10_code="G43.009",
        today_assessment="Migraine without aura, start sumatriptan",
        background="History of migraines since 2018",
        note_uuid="note-uuid-123",
        command_uuid="cmd-uuid-456",
    )


def test_build_with_missing_fields_defaults_to_empty() -> None:
    parser = DiagnoseParser()
    with patch("hyperscribe.scribe.commands.diagnose.DiagnoseCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        icd10_code="",
        today_assessment="",
        background="",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_none_values_defaults_to_empty() -> None:
    parser = DiagnoseParser()
    data = {
        "icd10_code": None,
        "today_assessment": None,
        "background": None,
    }
    with patch("hyperscribe.scribe.commands.diagnose.DiagnoseCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        icd10_code="",
        today_assessment="",
        background="",
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_command_type() -> None:
    parser = DiagnoseParser()
    assert parser.command_type == "diagnose"


def test_data_field_is_none() -> None:
    parser = DiagnoseParser()
    assert parser.data_field is None


def test_validate_requires_icd10_code() -> None:
    """Hard block: an uncoded diagnosis is rejected on the insert path."""
    parser = DiagnoseParser()
    assert "Diagnosis is missing an ICD-10 code" in parser.validate({"icd10_code": "", "today_assessment": "x"})
    assert "Diagnosis is missing an ICD-10 code" in parser.validate({"today_assessment": "x"})
    assert parser.validate({"icd10_code": "F33.1", "today_assessment": "x"}) == []


def test_validate_flags_long_assessment() -> None:
    parser = DiagnoseParser()
    errors = parser.validate({"icd10_code": "F33.1", "today_assessment": "x" * 2049})
    assert "Assessment text exceeds 2048 characters" in errors
