from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.commands.adjust_prescription import AdjustPrescriptionParser


def _good_data(**overrides: Any) -> dict[str, Any]:
    """Payload that satisfies every required field in canvas-core's schema."""
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
    parser = AdjustPrescriptionParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = AdjustPrescriptionParser()
    assert parser.extract_all("some text") == []


# ---- validate(): canvas-core required-field coverage ---------------------


def test_validate_clean_payload_returns_no_errors() -> None:
    parser = AdjustPrescriptionParser()
    assert parser.validate(_good_data()) == []


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
    """Mirrors the failure on Brigade note 20746 (refills: null)."""
    parser = AdjustPrescriptionParser()
    bad = _good_data(**{field: None})
    errors = parser.validate(bad)
    assert any(fragment in e for e in errors), errors


def test_validate_note_to_pharmacist_uses_210_char_limit() -> None:
    """Regression: previously the parser accepted up to 1024 chars, but
    canvas-core caps note_to_pharmacist at 210."""
    parser = AdjustPrescriptionParser()
    over = _good_data(note_to_pharmacist="x" * 211)
    errors = parser.validate(over)
    assert any("210" in e for e in errors)


def test_validate_change_medication_to_optional() -> None:
    parser = AdjustPrescriptionParser()
    # Adjust prescription accepts a change_medication_to (new_fdb_code) — but
    # also accepts None to mean "keep the existing medication".
    assert parser.validate(_good_data(new_fdb_code=None)) == []
    assert parser.validate(_good_data(new_fdb_code="123456")) == []
    # An empty string is a UI bug — the user opened the search but didn't pick.
    errors = parser.validate(_good_data(new_fdb_code="   "))
    assert any("New medication code" in e for e in errors)


# ---- validate_against_patient(): chart-state guard ------------------------


def test_validate_against_patient_skips_when_fdb_code_missing() -> None:
    """If shape validation already failed there's no point hitting the DB."""
    parser = AdjustPrescriptionParser()
    assert parser.validate_against_patient({"fdb_code": ""}, "note-uuid") == []


def test_validate_against_patient_handles_missing_note() -> None:
    parser = AdjustPrescriptionParser()
    with patch("hyperscribe.scribe.commands.adjust_prescription.Note") as mock_note:
        from canvas_sdk.v1.data.note import Note as RealNote

        mock_note.objects.values_list.return_value.get.side_effect = RealNote.DoesNotExist
        mock_note.DoesNotExist = RealNote.DoesNotExist
        errors = parser.validate_against_patient({"fdb_code": "123"}, "missing-note")

    assert any("Note not found" in e for e in errors)


def test_validate_against_patient_passes_when_medication_active() -> None:
    parser = AdjustPrescriptionParser()
    with (
        patch("hyperscribe.scribe.commands.adjust_prescription.Note") as mock_note,
        patch("hyperscribe.scribe.commands.adjust_prescription.Medication") as mock_med,
    ):
        mock_note.objects.values_list.return_value.get.return_value = "patient-1"
        mock_med.objects.filter.return_value.exists.return_value = True
        errors = parser.validate_against_patient({"fdb_code": "123"}, "note-uuid")

    assert errors == []


def test_validate_against_patient_rejects_when_medication_inactive() -> None:
    parser = AdjustPrescriptionParser()
    with (
        patch("hyperscribe.scribe.commands.adjust_prescription.Note") as mock_note,
        patch("hyperscribe.scribe.commands.adjust_prescription.Medication") as mock_med,
    ):
        mock_note.objects.values_list.return_value.get.return_value = "patient-1"
        mock_med.objects.filter.return_value.exists.return_value = False
        errors = parser.validate_against_patient({"fdb_code": "999"}, "note-uuid")

    assert any("not active on this patient" in e for e in errors)


# ---- build()-level smoke tests (existing behavior) ------------------------


def test_build_with_all_fields() -> None:
    parser = AdjustPrescriptionParser()
    data = {
        "fdb_code": "285665",
        "sig": "Take 1 tablet daily",
        "days_supply": 30,
        "quantity_to_dispense": 30,
        "refills": 2,
        "substitutions": "allowed",
    }
    with patch("hyperscribe.scribe.commands.adjust_prescription.AdjustPrescriptionCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.Substitutions.ALLOWED = "ALLOWED"
        mock_cmd.Substitutions.NOT_ALLOWED = "NOT_ALLOWED"
        with patch.object(parser, "_resolve_prescriber", return_value="provider-123"):
            parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once()
    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["fdb_code"] == "285665"
    assert call_kwargs["sig"] == "Take 1 tablet daily"
    assert call_kwargs["note_uuid"] == "note-uuid"


def test_build_with_missing_fields() -> None:
    parser = AdjustPrescriptionParser()
    with patch("hyperscribe.scribe.commands.adjust_prescription.AdjustPrescriptionCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        with patch.object(parser, "_resolve_prescriber", return_value=None):
            parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once()
    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["fdb_code"] is None
    assert call_kwargs["sig"] == ""


def test_command_type() -> None:
    assert AdjustPrescriptionParser().command_type == "adjust_prescription"


def test_data_field_is_none() -> None:
    assert AdjustPrescriptionParser().data_field is None


def test_to_effects_returns_originate_and_review() -> None:
    parser = AdjustPrescriptionParser()
    command = MagicMock()
    command.originate.return_value = MagicMock()
    command.review.return_value = MagicMock()

    effects = parser.to_effects(command)

    assert len(effects) == 2
    command.originate.assert_called_once()
    command.review.assert_called_once()
