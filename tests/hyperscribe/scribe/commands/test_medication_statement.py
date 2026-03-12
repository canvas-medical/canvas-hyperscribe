from unittest.mock import MagicMock, patch

from canvas_sdk.commands.constants import CodeSystems

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.medication_statement import (
    MedicationParser,
    _parse_medication_lines,
    _unstructured_coding,
)


def test_parse_medication_lines_bullets() -> None:
    text = "- Lisinopril 10mg\n- Metformin 500mg\n* Atorvastatin 20mg"
    assert _parse_medication_lines(text) == [
        "Lisinopril 10mg",
        "Metformin 500mg",
        "Atorvastatin 20mg",
    ]


def test_parse_medication_lines_numbers() -> None:
    text = "1. Lisinopril 10mg\n2) Metformin 500mg\n3. Atorvastatin 20mg"
    assert _parse_medication_lines(text) == [
        "Lisinopril 10mg",
        "Metformin 500mg",
        "Atorvastatin 20mg",
    ]


def test_parse_medication_lines_plain() -> None:
    text = "Lisinopril 10mg\nMetformin 500mg"
    assert _parse_medication_lines(text) == ["Lisinopril 10mg", "Metformin 500mg"]


def test_parse_medication_lines_empty_lines_skipped() -> None:
    text = "Lisinopril 10mg\n\n  \nMetformin 500mg"
    assert _parse_medication_lines(text) == ["Lisinopril 10mg", "Metformin 500mg"]


def test_parse_medication_lines_empty_string() -> None:
    assert _parse_medication_lines("") == []


def test_extract_all_multiple() -> None:
    parser = MedicationParser()
    proposals = parser.extract_all("- Lisinopril 10mg\n- Metformin 500mg")
    assert len(proposals) == 2
    assert proposals[0].command_type == "medication_statement"
    assert proposals[0].display == "Lisinopril 10mg"
    assert proposals[0].data == {
        "medication_text": "Lisinopril 10mg",
        "fdb_code": _unstructured_coding("Lisinopril 10mg"),
    }
    assert proposals[1].display == "Metformin 500mg"
    assert proposals[1].data == {
        "medication_text": "Metformin 500mg",
        "fdb_code": _unstructured_coding("Metformin 500mg"),
    }


def test_extract_all_single() -> None:
    parser = MedicationParser()
    proposals = parser.extract_all("Ibuprofen 400mg")
    assert len(proposals) == 1
    assert proposals[0].display == "Ibuprofen 400mg"


def test_extract_all_empty() -> None:
    parser = MedicationParser()
    assert parser.extract_all("") == []
    assert parser.extract_all("   ") == []


def test_extract_returns_first_line() -> None:
    parser = MedicationParser()
    proposal = parser.extract("- Lisinopril 10mg\n- Metformin 500mg")
    assert proposal is not None
    assert proposal.command_type == "medication_statement"
    assert proposal.display == "Lisinopril 10mg"


def test_extract_empty_returns_none() -> None:
    parser = MedicationParser()
    assert parser.extract("") is None
    assert parser.extract("   ") is None


def test_build_with_string_fdb_code() -> None:
    """When data has a string fdb_code (from Science search), build uses it directly."""
    parser = MedicationParser()
    cmd = parser.build(
        {"medication_text": "Lisinopril 10mg", "fdb_code": "12345"},
        "note-uuid",
        "cmd-uuid",
    )
    assert cmd.fdb_code == "12345"
    assert cmd.note_uuid == "note-uuid"


def test_build_with_dict_fdb_code_structured() -> None:
    """When data has a dict fdb_code with FDB system (from recommender), extract the plain code string."""
    parser = MedicationParser()
    cmd = parser.build(
        {
            "medication_text": "Lisinopril 10mg Tablet",
            "fdb_code": {
                "system": "http://www.fdbhealth.com/",
                "code": "d00350",
                "display": "Lisinopril 10mg Tablet",
            },
        },
        "note-uuid",
        "cmd-uuid",
    )
    assert cmd.fdb_code == "d00350"
    assert cmd.note_uuid == "note-uuid"


def test_build_with_dict_fdb_code_unstructured() -> None:
    """When data has a dict fdb_code (from extraction), build converts to Coding."""
    parser = MedicationParser()
    cmd = parser.build(
        {
            "medication_text": "Lisinopril 10mg",
            "fdb_code": _unstructured_coding("Lisinopril 10mg"),
        },
        "note-uuid",
        "cmd-uuid",
    )
    assert isinstance(cmd.fdb_code, dict)
    assert cmd.fdb_code["system"] == CodeSystems.UNSTRUCTURED
    assert cmd.fdb_code["display"] == "Lisinopril 10mg"


def test_build_without_fdb_code_falls_back_to_unstructured() -> None:
    """When data has no fdb_code, build creates UNSTRUCTURED coding."""
    parser = MedicationParser()
    cmd = parser.build({"medication_text": "Some unknown med"}, "note-uuid", "cmd-uuid")
    assert isinstance(cmd.fdb_code, dict)
    assert cmd.fdb_code["system"] == CodeSystems.UNSTRUCTURED
    assert cmd.fdb_code["display"] == "Some unknown med"
    assert cmd.note_uuid == "note-uuid"


def test_build_empty_medication_text() -> None:
    parser = MedicationParser()
    cmd = parser.build({"medication_text": ""}, "note-uuid", "cmd-uuid")
    assert isinstance(cmd.fdb_code, dict)
    assert cmd.fdb_code["system"] == CodeSystems.UNSTRUCTURED


def test_build_with_sig() -> None:
    parser = MedicationParser()
    cmd = parser.build(
        {"medication_text": "Lisinopril 10mg", "sig": "Take 1 tablet daily"},
        "note-uuid",
        "cmd-uuid",
    )
    assert cmd.sig == "Take 1 tablet daily"


def test_build_without_sig_defaults_to_none() -> None:
    parser = MedicationParser()
    cmd = parser.build({"medication_text": "Lisinopril 10mg"}, "note-uuid", "cmd-uuid")
    assert cmd.sig is None


def test_build_empty_sig_defaults_to_none() -> None:
    parser = MedicationParser()
    cmd = parser.build(
        {"medication_text": "Lisinopril 10mg", "sig": ""},
        "note-uuid",
        "cmd-uuid",
    )
    assert cmd.sig is None


# --- annotate_duplicates ---


@patch("hyperscribe.scribe.commands.medication_statement.MedicationCoding")
def test_annotate_duplicates_match(
    mock_coding_cls: MagicMock,
) -> None:
    mock_patient = MagicMock()
    mock_patient.id = "patient-key"
    mock_note = MagicMock()
    mock_note.patient = mock_patient

    mock_coding_cls.objects.filter.return_value.values_list.return_value = ["Lisinopril 10mg Tablet"]

    proposals = [
        CommandProposal(
            command_type="medication_statement", display="Lisinopril 10mg", data={"medication_text": "Lisinopril 10mg"}
        ),
        CommandProposal(
            command_type="medication_statement", display="Metformin 500mg", data={"medication_text": "Metformin 500mg"}
        ),
        CommandProposal(command_type="hpi", display="Pain", data={"narrative": "Pain"}),
    ]
    MedicationParser().annotate_duplicates(proposals, mock_note)

    assert proposals[0].already_documented is True
    assert proposals[1].already_documented is False
    assert proposals[2].already_documented is False


def test_annotate_duplicates_no_medications() -> None:
    mock_note = MagicMock()
    proposals = [
        CommandProposal(command_type="hpi", display="Pain", data={"narrative": "Pain"}),
    ]
    MedicationParser().annotate_duplicates(proposals, mock_note)
    assert proposals[0].already_documented is False


@patch("hyperscribe.scribe.commands.medication_statement.MedicationCoding")
def test_annotate_duplicates_no_patient(
    mock_coding_cls: MagicMock,
) -> None:
    mock_note = MagicMock()
    mock_note.patient = None

    proposals = [
        CommandProposal(
            command_type="medication_statement", display="Lisinopril", data={"medication_text": "Lisinopril"}
        ),
    ]
    MedicationParser().annotate_duplicates(proposals, mock_note)
    assert proposals[0].already_documented is False
