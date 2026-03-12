from unittest.mock import MagicMock, patch

from canvas_sdk.commands.commands.allergy import Allergen, AllergenType, AllergyCommand

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.allergy import AllergyParser


def test_extract_single_allergy() -> None:
    parser = AllergyParser()
    proposal = parser.extract("Penicillin (rash)")
    assert proposal is not None
    assert proposal.command_type == "allergy"
    assert proposal.display == "Penicillin (rash)"
    assert proposal.data["allergy_text"] == "Penicillin (rash)"
    assert proposal.data["concept_id"] is None
    assert proposal.data["concept_id_type"] is None


def test_extract_all_multiple() -> None:
    parser = AllergyParser()
    proposals = parser.extract_all("Penicillin (rash)\nSulfa drugs (hives)\nAspirin")
    assert len(proposals) == 3
    assert proposals[0].display == "Penicillin (rash)"
    assert proposals[1].display == "Sulfa drugs (hives)"
    assert proposals[2].display == "Aspirin"
    assert all(p.command_type == "allergy" for p in proposals)


def test_extract_strips_bullets() -> None:
    parser = AllergyParser()
    proposals = parser.extract_all("- Penicillin\n- Sulfa drugs\n* Aspirin")
    assert len(proposals) == 3
    assert proposals[0].display == "Penicillin"
    assert proposals[1].display == "Sulfa drugs"
    assert proposals[2].display == "Aspirin"


def test_extract_empty_text() -> None:
    parser = AllergyParser()
    assert parser.extract("") is None
    assert parser.extract("   ") is None
    assert parser.extract_all("") == []


def test_build_with_concept_id() -> None:
    parser = AllergyParser()
    data = {
        "allergy_text": "Penicillin (rash)",
        "concept_id": 12345,
        "concept_id_type": 1,
    }
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        result = parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy=Allergen(concept_id=12345, concept_type=AllergenType(1)),
        narrative="Penicillin (rash)",
        severity=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )
    assert result is inst


def test_build_without_concept_id() -> None:
    parser = AllergyParser()
    data = {
        "allergy_text": "Penicillin (rash)",
        "concept_id": None,
        "concept_id_type": None,
    }
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        result = parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="Penicillin (rash)",
        severity=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )
    assert result is inst


def test_build_missing_fields_defaults() -> None:
    parser = AllergyParser()
    data: dict[str, object] = {}
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="",
        severity=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_with_severity_and_reaction() -> None:
    parser = AllergyParser()
    data = {
        "allergy_text": "Penicillin",
        "concept_id": None,
        "concept_id_type": None,
        "reaction": "rash and hives",
        "severity": "severe",
    }
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        mock_cmd.Severity = AllergyCommand.Severity
        result = parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="rash and hives",
        severity=AllergyCommand.Severity.SEVERE,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )
    assert result is inst


def test_build_reaction_takes_precedence_over_allergy_text() -> None:
    parser = AllergyParser()
    data = {
        "allergy_text": "Penicillin",
        "concept_id": None,
        "concept_id_type": None,
        "reaction": "anaphylaxis",
    }
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        mock_cmd.Severity = AllergyCommand.Severity
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="anaphylaxis",
        severity=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


def test_build_invalid_severity_ignored() -> None:
    parser = AllergyParser()
    data = {
        "allergy_text": "Penicillin",
        "concept_id": None,
        "concept_id_type": None,
        "severity": "extreme",
    }
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        mock_cmd.Severity = AllergyCommand.Severity
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="Penicillin",
        severity=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


# --- annotate_duplicates ---


@patch("hyperscribe.scribe.commands.allergy.AllergyIntoleranceCoding")
def test_annotate_duplicates_match(
    mock_coding_cls: MagicMock,
) -> None:
    mock_patient = MagicMock()
    mock_patient.id = "patient-key"
    mock_note = MagicMock()
    mock_note.patient = mock_patient

    mock_coding_cls.objects.filter.return_value.committed.return_value.values_list.return_value = ["Penicillin G"]

    proposals = [
        CommandProposal(command_type="allergy", display="Penicillin", data={"allergy_text": "Penicillin"}),
        CommandProposal(command_type="allergy", display="Sulfa drugs", data={"allergy_text": "Sulfa drugs"}),
        CommandProposal(command_type="hpi", display="Pain", data={"narrative": "Pain"}),
    ]
    AllergyParser().annotate_duplicates(proposals, mock_note)

    assert proposals[0].already_documented is True  # substring match
    assert proposals[1].already_documented is False
    assert proposals[2].already_documented is False  # non-allergy untouched


def test_annotate_duplicates_no_allergies() -> None:
    mock_note = MagicMock()
    proposals = [
        CommandProposal(command_type="hpi", display="Pain", data={"narrative": "Pain"}),
    ]
    AllergyParser().annotate_duplicates(proposals, mock_note)
    assert proposals[0].already_documented is False


@patch("hyperscribe.scribe.commands.allergy.AllergyIntoleranceCoding")
def test_annotate_duplicates_no_patient(
    mock_coding_cls: MagicMock,
) -> None:
    mock_note = MagicMock()
    mock_note.patient = None

    proposals = [
        CommandProposal(command_type="allergy", display="Penicillin", data={"allergy_text": "Penicillin"}),
    ]
    AllergyParser().annotate_duplicates(proposals, mock_note)
    assert proposals[0].already_documented is False
