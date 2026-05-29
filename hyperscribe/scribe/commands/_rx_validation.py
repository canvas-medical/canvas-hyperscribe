"""Shared validation logic for prescription-style commands.

`prescribe`, `refill`, and `adjust_prescription` all funnel through the same
canvas-core ``Prescribe`` schema (``canvas_core.commands.definitions.prescribe``)
during the REVIEW step. That schema declares the following required fields:

- ``prescribe`` (medication) — required
- ``sig`` — required, max 1000 chars, ASCII-Surescripts only
- ``quantity_to_dispense`` — required, must be > 0, no trailing zero decimals
- ``type_to_dispense`` — required (dosage form / dispense unit)
- ``refills`` — required, integer in [0, 99]
- ``substitutions`` — required, ``allowed`` or ``not_allowed``
- ``prescriber`` — required
- ``note_to_pharmacist`` — optional, max **210** chars, ASCII-Surescripts only
  (NOTE: 210, not 1024 — Surescripts NewRx limit)

Originate succeeds with partial data, but the second ``REVIEW`` effect raises
``ValidationError("Command cannot be reviewed due to incomplete data. Please
fill in all required fields.")`` and rolls back the whole transaction. The
``insert-commands`` HTTP response is already 200 by then, so the UI thinks the
write worked. Catching incomplete payloads here — before the SDK call — keeps
the transaction from ever opening, surfaces a structured error to the
front-end, and makes the failure debuggable from the audit log.

This module is intentionally framework-agnostic: pure functions that take a
``data`` dict and return a list of human-readable error strings.
"""

from __future__ import annotations

import re

# NOTE: only ``Decimal`` is imported here. The Canvas plugin sandbox allowlists
# ``Decimal`` from ``decimal`` but rejects ``InvalidOperation`` — importing it
# raises ``ImportError`` at plugin-load time and de-registers every handler
# downstream of this module (the whole Scribe UI 404s). ``InvalidOperation`` is
# a subclass of ``ArithmeticError``, so the ``except`` below still catches it.
from decimal import Decimal
from typing import Any

# Mirrors canvas_core.commands.definitions.prescribe.RE_INVALID_CHARACTERS.
# Surescripts only allows printable ASCII (space through tilde) for sig and
# note_to_pharmacist; newlines, smart quotes, and control characters all fail
# the upstream validator.
_RE_INVALID_CHARACTERS = re.compile(r"[^ -~]")

# canvas-core constants.
SIG_MAX_LENGTH = 1000
NOTE_TO_PHARMACIST_MAX_LENGTH = 210
REFILLS_MIN = 0
REFILLS_MAX = 99


def _has_value(value: Any) -> bool:
    """Treat ``None``, empty string, and empty container as missing."""
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _validate_required_string(data: dict[str, Any], field: str, label: str, errors: list[str]) -> None:
    if not _has_value(data.get(field)):
        errors.append(f"{label} is required")


def _validate_quantity_to_dispense(value: Any, errors: list[str]) -> None:
    """Required, must parse to a positive Decimal, no trailing-zero decimals."""
    if not _has_value(value):
        errors.append("Quantity to dispense is required")
        return
    try:
        decimal_value = Decimal(str(value))
    except (ArithmeticError, ValueError):
        errors.append("Quantity to dispense must be a number")
        return
    # Decimal('nan') and Decimal('Infinity') both parse cleanly; NaN raises on
    # comparison and Infinity slips silently into PrescribeCommand and blows
    # up at int() conversion downstream. Reject both as non-numeric.
    if not decimal_value.is_finite():
        errors.append("Quantity to dispense must be a number")
        return
    if decimal_value <= 0:
        errors.append("Quantity to dispense must be greater than 0")
        return
    str_value = str(value).strip()
    # Mirror canvas_core.commands.definitions.prescribe.dispense_quantity_validator:
    # reject trailing zeros after a decimal point ("1.0", "1.") because the
    # Surescripts NewRx wire format rejects them.
    if "." in str_value and (str_value.endswith("0") or str_value.endswith(".")):
        errors.append("Quantity to dispense cannot have trailing zeroes")


def _validate_refills(value: Any, errors: list[str]) -> None:
    """Required, integer in [0, 99]."""
    if value is None or value == "":
        errors.append("Refills is required")
        return
    # int(10.5) silently truncates to 10 and int(-0.5) silently truncates to 0
    # (which then passes the range check). Reject non-integer floats up front
    # rather than letting a fractional refill count round into a valid value.
    if isinstance(value, float) and not value.is_integer():
        errors.append("Refills must be an integer")
        return
    try:
        refills = int(value)
    except (TypeError, ValueError, OverflowError):
        # OverflowError fires on int(float('inf')); not a subclass of ValueError.
        errors.append("Refills must be an integer")
        return
    if refills < REFILLS_MIN or refills > REFILLS_MAX:
        errors.append(f"Refills must be between {REFILLS_MIN} and {REFILLS_MAX}")


def _validate_days_supply(value: Any, errors: list[str]) -> None:
    """Optional, but if present must be a non-negative integer."""
    if value is None or value == "":
        return
    if isinstance(value, float) and not value.is_integer():
        errors.append("Days supply must be an integer")
        return
    try:
        days = int(value)
    except (TypeError, ValueError, OverflowError):
        errors.append("Days supply must be an integer")
        return
    if days < 0:
        errors.append("Days supply must be non-negative")


def _validate_substitutions(value: Any, errors: list[str]) -> None:
    """Required. Must be ``allowed`` or ``not_allowed``."""
    # canvas-core schema declares substitutions required with default
    # ``ALLOWED``. The SDK passes ``None`` straight through and the schema
    # default does NOT kick in for SDK-originated commands, so we treat
    # missing-or-empty as a validation failure to avoid the REVIEW reject.
    if not _has_value(value):
        errors.append("Substitutions is required (allowed / not_allowed)")
        return
    if value not in ("allowed", "not_allowed"):
        errors.append("Substitutions must be 'allowed' or 'not_allowed'")


def _validate_sig(value: Any, errors: list[str]) -> None:
    """Required, max ``SIG_MAX_LENGTH`` chars, ASCII-Surescripts."""
    if not _has_value(value):
        errors.append("Sig is required")
        return
    text = str(value)
    if len(text) > SIG_MAX_LENGTH:
        errors.append(f"Sig exceeds {SIG_MAX_LENGTH} characters")
    if _RE_INVALID_CHARACTERS.search(text):
        errors.append("Sig contains characters not allowed by Surescripts (remove newlines, tabs, and non-ASCII)")


def _validate_note_to_pharmacist(value: Any, errors: list[str]) -> None:
    """Optional. Max ``NOTE_TO_PHARMACIST_MAX_LENGTH``, ASCII-Surescripts."""
    if value is None or value == "":
        return
    text = str(value)
    if len(text) > NOTE_TO_PHARMACIST_MAX_LENGTH:
        errors.append(f"Note to pharmacist exceeds {NOTE_TO_PHARMACIST_MAX_LENGTH} characters")
    if _RE_INVALID_CHARACTERS.search(text):
        errors.append(
            "Note to pharmacist contains characters not allowed by Surescripts (remove newlines, tabs, and non-ASCII)"
        )


def _validate_type_to_dispense(data: dict[str, Any], errors: list[str]) -> None:
    """Required. The plugin builds a ``ClinicalQuantity`` from this string."""
    if not _has_value(data.get("type_to_dispense")):
        errors.append("Dispense type is required")


def _validate_optional_change_medication_to(value: Any, errors: list[str]) -> None:
    """``new_fdb_code`` is optional for adjust_prescription, but if a string is
    supplied it must be non-empty after stripping."""
    if value is None:
        return
    if not isinstance(value, str):
        errors.append("New medication code must be a string")
        return
    if value.strip() == "":
        errors.append(
            "New medication code is empty — leave it unset to keep the existing medication, or pick a replacement"
        )


def validate_rx_payload(
    data: dict[str, Any],
    *,
    require_fdb_code: bool = True,
    allow_change_medication_to: bool = False,
) -> list[str]:
    """Run the full canvas-core-aligned validation against an Rx payload.

    Args:
        data: the proposal ``data`` dict from the front-end.
        require_fdb_code: whether the source medication FDB code is required.
            All three command types (prescribe/refill/adjust_prescription)
            require it — refill and adjust_prescription identify the existing
            medication, prescribe identifies the new medication. Set False
            only when an alternative medication identifier (compound med id,
            inline compound med data) is supplied.
        allow_change_medication_to: when True (adjust_prescription only),
            also runs the optional-but-validated check on ``new_fdb_code``.
    """
    errors: list[str] = []

    if require_fdb_code:
        _validate_required_string(data, "fdb_code", "Medication", errors)

    _validate_sig(data.get("sig"), errors)
    _validate_quantity_to_dispense(data.get("quantity_to_dispense"), errors)
    _validate_type_to_dispense(data, errors)
    _validate_refills(data.get("refills"), errors)
    _validate_substitutions(data.get("substitutions"), errors)
    _validate_days_supply(data.get("days_supply"), errors)
    _validate_note_to_pharmacist(data.get("note_to_pharmacist"), errors)

    if allow_change_medication_to:
        _validate_optional_change_medication_to(data.get("new_fdb_code"), errors)

    return errors
