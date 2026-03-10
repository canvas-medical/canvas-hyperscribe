from unittest.mock import MagicMock, patch

from canvas_sdk.commands.commands.allergy import Allergen, AllergenType

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
        result = parser.build(data, "note-uuid")

    mock_cmd.assert_called_once_with(
        allergy=Allergen(concept_id=12345, concept_type=AllergenType(1)),
        narrative="Penicillin (rash)",
        note_uuid="note-uuid",
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
        result = parser.build(data, "note-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="Penicillin (rash)",
        note_uuid="note-uuid",
    )
    assert result is inst


def test_build_missing_fields_defaults() -> None:
    parser = AllergyParser()
    data: dict[str, object] = {}
    with patch("hyperscribe.scribe.commands.allergy.AllergyCommand") as mock_cmd:
        inst = MagicMock()
        mock_cmd.return_value = inst
        parser.build(data, "note-uuid")

    mock_cmd.assert_called_once_with(
        allergy=None,
        narrative="",
        note_uuid="note-uuid",
    )
