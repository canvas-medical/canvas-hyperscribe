"""Tests for ``RefillParser`` validation.

The refill flow shares the canvas-core ``Prescribe`` schema with adjust
prescription and prescribe, so the same set of required-field gates applies.
This file focuses on the validation paths added as part of the work to
prevent the silent-success-then-rollback failure mode where /insert-commands
returned 200 but REVIEW raised ``ValidationError``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from hyperscribe.scribe.commands.refill import RefillParser


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


def test_validate_clean_payload_returns_no_errors() -> None:
    assert RefillParser().validate(_good_data()) == []


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
    errors = RefillParser().validate(_good_data(**{field: None}))
    assert any(fragment in e for e in errors), errors


def test_validate_note_to_pharmacist_uses_210_char_limit() -> None:
    """Regression: previously the parser accepted up to 1024 chars."""
    over = _good_data(note_to_pharmacist="x" * 211)
    errors = RefillParser().validate(over)
    assert any("210" in e for e in errors)


def test_validate_against_patient_skips_when_fdb_code_missing() -> None:
    assert RefillParser().validate_against_patient({"fdb_code": ""}, "note-uuid") == []


def test_validate_against_patient_passes_when_medication_active() -> None:
    parser = RefillParser()
    with (
        patch("hyperscribe.scribe.commands.refill.Note") as mock_note,
        patch("hyperscribe.scribe.commands.refill.Medication") as mock_med,
    ):
        mock_note.objects.values_list.return_value.get.return_value = "patient-1"
        mock_med.objects.committed.return_value.for_patient.return_value.filter.return_value.exists.return_value = True
        errors = parser.validate_against_patient({"fdb_code": "123"}, "note-uuid")

    assert errors == []
    # Confirm the entered_in_error-excluding manager chain was used (not a
    # plain .filter, which would let retracted Medication rows pass).
    mock_med.objects.committed.assert_called_once_with()
    mock_med.objects.committed.return_value.for_patient.assert_called_once_with("patient-1")
    # Confirm the patient UUID is fetched via patient__id (double underscore).
    # Single-underscore "patient_id" returns the FK column (integer dbid),
    # which never matches for_patient() — every refill would be rejected.
    mock_note.objects.values_list.assert_called_once_with("patient__id", flat=True)


def test_validate_against_patient_rejects_when_medication_inactive() -> None:
    parser = RefillParser()
    with (
        patch("hyperscribe.scribe.commands.refill.Note") as mock_note,
        patch("hyperscribe.scribe.commands.refill.Medication") as mock_med,
    ):
        mock_note.objects.values_list.return_value.get.return_value = "patient-1"
        mock_med.objects.committed.return_value.for_patient.return_value.filter.return_value.exists.return_value = False
        errors = parser.validate_against_patient({"fdb_code": "999"}, "note-uuid")

    assert any("not active on this patient" in e for e in errors)


def test_command_type() -> None:
    assert RefillParser().command_type == "refill"
