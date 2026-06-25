from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.scribe.commands.prescription import PrescriptionParser


def _good_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "fdb_code": "285665",
        "sig": "Take 1 tablet by mouth daily",
        "quantity_to_dispense": 30,
        "type_to_dispense": "C48480",
        "refills": 2,
        "substitutions": "allowed",
    }
    data.update(overrides)
    return data


def test_extract_returns_none() -> None:
    parser = PrescriptionParser()
    assert parser.extract("Lisinopril 10mg") is None


# ---- validate(): canvas-core required-field coverage ----------------------


def test_validate_clean_payload_returns_no_errors() -> None:
    assert PrescriptionParser().validate(_good_data()) == []


@pytest.mark.parametrize(
    "field,fragment",
    [
        ("fdb_code", "Medication"),
        ("sig", "Sig"),
        ("quantity_to_dispense", "Quantity to dispense"),
        ("type_to_dispense", "Dispense type"),
        ("refills", "Refills"),
        ("substitutions", "Substitutions"),
    ],
)
def test_validate_each_required_field(field: str, fragment: str) -> None:
    errors = PrescriptionParser().validate(_good_data(**{field: None}))
    assert any(fragment in e for e in errors), errors


def test_validate_note_to_pharmacist_uses_210_char_limit() -> None:
    """Regression: previously the parser accepted up to 1024 chars."""
    over = _good_data(note_to_pharmacist="x" * 211)
    errors = PrescriptionParser().validate(over)
    assert any("210" in e for e in errors)


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


def test_build_treats_empty_days_supply_as_absent() -> None:
    """`int('')` raises ValueError. The validator treats '' as 'not provided',
    so build() must also — otherwise a form that cleared the days_supply
    field crashes the request with an uncaught ValueError → HTTP 500."""
    parser = PrescriptionParser()
    with patch("hyperscribe.scribe.commands.prescription.PrescribeCommand") as mock_cmd:
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build({"days_supply": ""}, "note-uuid", "cmd-uuid")

    assert mock_cmd.call_args.kwargs["days_supply"] is None


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
