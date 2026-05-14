"""Tests for the shared Rx validation helper used by prescribe / refill /
adjust_prescription parsers.

The behavior under test mirrors the canvas-core ``Prescribe`` schema in
``canvas_core.commands.definitions.prescribe`` — every required field that
schema declares MUST trip ``validate_rx_payload``, otherwise the command
will originate successfully and then fail at REVIEW with the generic
"Command cannot be reviewed due to incomplete data" error that motivated
this work (see canvas-medical/canvas-hyperscribe#XXX).
"""

from __future__ import annotations

from typing import Any

import pytest

from hyperscribe.scribe.commands._rx_validation import (
    NOTE_TO_PHARMACIST_MAX_LENGTH,
    REFILLS_MAX,
    REFILLS_MIN,
    SIG_MAX_LENGTH,
    validate_rx_payload,
)


def _good_payload(**overrides: Any) -> dict[str, Any]:
    """Build a payload that satisfies every required-field check.

    Tests should start from this and override the field they want to
    exercise — that way a future required field is caught everywhere.
    """
    payload = {
        "fdb_code": "285665",
        "sig": "Take 1 tablet by mouth daily",
        "quantity_to_dispense": 30,
        "type_to_dispense": "C48480",
        "refills": 2,
        "substitutions": "allowed",
        "days_supply": 30,
        "note_to_pharmacist": "Patient prefers generic",
    }
    payload.update(overrides)
    return payload


def test_good_payload_has_no_errors() -> None:
    assert validate_rx_payload(_good_payload()) == []


# ---- Required fields --------------------------------------------------------


@pytest.mark.parametrize(
    "field,label",
    [
        ("fdb_code", "Medication"),
        ("sig", "Sig"),
    ],
)
def test_required_string_fields(field: str, label: str) -> None:
    """Missing or whitespace-only strings fail validation."""
    for missing in (None, "", "   "):
        errors = validate_rx_payload(_good_payload(**{field: missing}))
        assert any(e.startswith(label) and "required" in e for e in errors), errors


def test_quantity_to_dispense_required() -> None:
    errors = validate_rx_payload(_good_payload(quantity_to_dispense=None))
    assert "Quantity to dispense is required" in errors


def test_quantity_to_dispense_must_be_positive() -> None:
    for bad in (0, -1, "0", "-5"):
        errors = validate_rx_payload(_good_payload(quantity_to_dispense=bad))
        assert any("greater than 0" in e for e in errors), (bad, errors)


def test_quantity_to_dispense_rejects_trailing_zero_decimals() -> None:
    """Mirrors canvas-core's ``dispense_quantity_validator``."""
    for bad in ("1.0", "10.", "5.20"):
        errors = validate_rx_payload(_good_payload(quantity_to_dispense=bad))
        assert any("trailing zeroes" in e for e in errors), (bad, errors)


def test_quantity_to_dispense_accepts_clean_decimals() -> None:
    for good in (30, 30.5, "30", "30.5", "1.25"):
        assert validate_rx_payload(_good_payload(quantity_to_dispense=good)) == []


def test_quantity_to_dispense_rejects_garbage() -> None:
    errors = validate_rx_payload(_good_payload(quantity_to_dispense="abc"))
    assert any("must be a number" in e for e in errors)


def test_quantity_to_dispense_rejects_nan() -> None:
    """``Decimal('nan')`` parses cleanly but comparisons raise InvalidOperation
    — guard or this returns HTTP 500 instead of the structured 400."""
    for nan_input in ("nan", "NaN", "-nan"):
        errors = validate_rx_payload(_good_payload(quantity_to_dispense=nan_input))
        assert any("must be a number" in e for e in errors), (nan_input, errors)


def test_type_to_dispense_required() -> None:
    errors = validate_rx_payload(_good_payload(type_to_dispense=None))
    assert "Dispense type is required" in errors


def test_refills_required() -> None:
    for missing in (None, ""):
        errors = validate_rx_payload(_good_payload(refills=missing))
        assert "Refills is required" in errors, errors


def test_refills_must_be_in_range() -> None:
    """The schema declares min=0 max=99."""
    errors = validate_rx_payload(_good_payload(refills=-1))
    assert any("between" in e for e in errors)
    errors = validate_rx_payload(_good_payload(refills=100))
    assert any("between" in e for e in errors)
    # Boundary values are allowed.
    assert validate_rx_payload(_good_payload(refills=REFILLS_MIN)) == []
    assert validate_rx_payload(_good_payload(refills=REFILLS_MAX)) == []


def test_refills_must_be_integer() -> None:
    errors = validate_rx_payload(_good_payload(refills="abc"))
    assert any("integer" in e for e in errors)


def test_substitutions_required() -> None:
    """canvas-core declares this required and the SDK does not default it."""
    for missing in (None, "", "   "):
        errors = validate_rx_payload(_good_payload(substitutions=missing))
        assert any("Substitutions" in e and "required" in e for e in errors), errors


def test_substitutions_must_be_known_value() -> None:
    errors = validate_rx_payload(_good_payload(substitutions="generic-please"))
    assert any("allowed" in e and "not_allowed" in e for e in errors)


def test_substitutions_accepts_both_values() -> None:
    for good in ("allowed", "not_allowed"):
        assert validate_rx_payload(_good_payload(substitutions=good)) == []


# ---- Optional fields with constraints --------------------------------------


def test_days_supply_optional_but_validated_when_present() -> None:
    assert validate_rx_payload(_good_payload(days_supply=None)) == []
    errors = validate_rx_payload(_good_payload(days_supply=-1))
    assert any("non-negative" in e for e in errors)
    errors = validate_rx_payload(_good_payload(days_supply="abc"))
    assert any("integer" in e for e in errors)


def test_sig_max_length() -> None:
    over = "a" * (SIG_MAX_LENGTH + 1)
    errors = validate_rx_payload(_good_payload(sig=over))
    assert any(f"exceeds {SIG_MAX_LENGTH}" in e for e in errors)


def test_sig_rejects_non_ascii_surescripts() -> None:
    """Surescripts NewRx wire format is ASCII printable only."""
    errors = validate_rx_payload(_good_payload(sig="Take 1 tab daily — see notes"))
    assert any("Surescripts" in e for e in errors)
    # Newlines are also not allowed.
    errors = validate_rx_payload(_good_payload(sig="Take 1 tab\ndaily"))
    assert any("Surescripts" in e for e in errors)


def test_note_to_pharmacist_max_length_is_210() -> None:
    """Critical regression test: the plugin previously allowed 1024 chars,
    which would silently fail at REVIEW because canvas-core caps it at 210."""
    over = "a" * (NOTE_TO_PHARMACIST_MAX_LENGTH + 1)
    errors = validate_rx_payload(_good_payload(note_to_pharmacist=over))
    assert any(
        f"exceeds {NOTE_TO_PHARMACIST_MAX_LENGTH}" in e for e in errors
    )
    # Exactly at the boundary is fine.
    at_limit = "a" * NOTE_TO_PHARMACIST_MAX_LENGTH
    assert validate_rx_payload(_good_payload(note_to_pharmacist=at_limit)) == []


def test_note_to_pharmacist_rejects_non_ascii_surescripts() -> None:
    errors = validate_rx_payload(_good_payload(note_to_pharmacist="Préfère générique"))
    assert any("Surescripts" in e for e in errors)


def test_note_to_pharmacist_optional_when_empty() -> None:
    for empty in (None, ""):
        assert validate_rx_payload(_good_payload(note_to_pharmacist=empty)) == []


# ---- Toggling required_fdb_code --------------------------------------------


def test_fdb_code_can_be_optional_for_compound_meds() -> None:
    """Compound prescriptions don't carry an fdb_code."""
    payload = _good_payload(fdb_code=None)
    errors = validate_rx_payload(payload, require_fdb_code=False)
    assert all("Medication" not in e for e in errors)


# ---- adjust_prescription's optional change_medication_to -------------------


def test_change_medication_to_optional_when_unset() -> None:
    payload = _good_payload()
    payload.pop("new_fdb_code", None)
    errors = validate_rx_payload(payload, allow_change_medication_to=True)
    assert errors == []


def test_change_medication_to_when_explicitly_none_is_fine() -> None:
    payload = _good_payload(new_fdb_code=None)
    errors = validate_rx_payload(payload, allow_change_medication_to=True)
    assert errors == []


def test_change_medication_to_rejects_blank_string() -> None:
    """Empty string is a UI bug: user opened the field but didn't pick a med."""
    payload = _good_payload(new_fdb_code="   ")
    errors = validate_rx_payload(payload, allow_change_medication_to=True)
    assert any("New medication code" in e for e in errors)


def test_change_medication_to_rejects_non_string() -> None:
    payload = _good_payload(new_fdb_code=12345)
    errors = validate_rx_payload(payload, allow_change_medication_to=True)
    assert any("must be a string" in e for e in errors)


# ---- Reproductions of the actual bug ---------------------------------------


def test_reproduces_brigade_note_20746_failure() -> None:
    """The note_uuid Tm90ZTo5MDoyMDc0Ng== failure had ``refills: null``.

    Before this validator existed, the proposal originated a command and
    then REVIEW raised ``ValidationError("Command cannot be reviewed due
    to incomplete data...")``, rolling back the transaction. We expect the
    new validator to catch this earlier with a clear "Refills is required"
    message.
    """
    payload = _good_payload(refills=None)
    errors = validate_rx_payload(payload, allow_change_medication_to=True)
    assert "Refills is required" in errors
