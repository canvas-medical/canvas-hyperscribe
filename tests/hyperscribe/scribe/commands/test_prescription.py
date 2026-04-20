from decimal import Decimal
from unittest.mock import MagicMock, patch

from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.scribe.commands.prescription import PrescriptionParser


def test_extract_returns_none() -> None:
    parser = PrescriptionParser()
    assert parser.extract("Lisinopril 10mg") is None


def test_build_full() -> None:
    parser = PrescriptionParser()
    data = {
        "fdb_code": "12345",
        "sig": "Take 1 tablet daily",
        "days_supply": 30,
        "quantity_to_dispense": 30,
        "refills": 3,
        "substitutions": "allowed",
        "note_to_pharmacist": "Patient prefers generic",
    }
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.Substitutions.ALLOWED = "ALLOWED"
        mock_cmd.Substitutions.NOT_ALLOWED = "NOT_ALLOWED"
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["fdb_code"] == "12345"
    assert call_kwargs["sig"] == "Take 1 tablet daily"
    assert call_kwargs["days_supply"] == 30
    assert call_kwargs["quantity_to_dispense"] == Decimal("30")
    assert call_kwargs["refills"] == 3
    assert call_kwargs["substitutions"] == "ALLOWED"
    assert call_kwargs["note_to_pharmacist"] == "Patient prefers generic"
    assert call_kwargs["note_uuid"] == "note-uuid"


def test_build_substitutions_not_allowed() -> None:
    parser = PrescriptionParser()
    data = {"fdb_code": "12345", "sig": "", "substitutions": "not_allowed"}
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.Substitutions.ALLOWED = "ALLOWED"
        mock_cmd.Substitutions.NOT_ALLOWED = "NOT_ALLOWED"
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    assert mock_cmd.call_args.kwargs["substitutions"] == "NOT_ALLOWED"


def test_build_minimal() -> None:
    parser = PrescriptionParser()
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["fdb_code"] is None
    assert call_kwargs["sig"] == ""
    assert call_kwargs["days_supply"] is None
    assert call_kwargs["quantity_to_dispense"] is None
    assert call_kwargs["refills"] is None
    assert call_kwargs["substitutions"] is None
    assert call_kwargs["note_to_pharmacist"] is None


def test_build_with_complete_clinical_quantity() -> None:
    """ClinicalQuantity with all fields (ndc + qualifier + description) is passed through."""
    parser = PrescriptionParser()
    data = {
        "sig": "Take 1 tablet daily",
        "type_to_dispense": "00093314705",
        "representative_ndc": "00093314705",
        "type_to_dispense_label": "Tablet",
    }
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    qty: ClinicalQuantity = mock_cmd.call_args.kwargs["type_to_dispense"]
    assert qty["representative_ndc"] == "00093314705"
    assert qty["ncpdp_quantity_qualifier_code"] == "00093314705"
    assert qty["description"] == "Tablet"


def test_build_with_partial_clinical_quantity() -> None:
    """ClinicalQuantity without display is valid — description is NotRequired."""
    parser = PrescriptionParser()
    data = {
        "sig": "Take 1 tablet daily",
        "type_to_dispense": "C48477",
        "representative_ndc": "00093314705",
    }
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    qty: ClinicalQuantity = mock_cmd.call_args.kwargs["type_to_dispense"]
    assert qty["representative_ndc"] == "00093314705"
    assert qty["ncpdp_quantity_qualifier_code"] == "C48477"
    assert "description" not in qty


def test_build_invalid_quantity_ignored() -> None:
    parser = PrescriptionParser()
    data = {"quantity_to_dispense": "not-a-number", "sig": ""}
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    assert mock_cmd.call_args.kwargs["quantity_to_dispense"] is None
