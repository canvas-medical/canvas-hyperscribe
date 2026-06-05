"""Shared validation for charge enrichment (diagnosis pointers + modifiers).

This is the single source of truth used by BOTH the frontend (to gate the
"Accept and sign" button) and the ``/enrich-charges`` write path (to reject
invalid payloads defensively). The caps come from CMS-1500 box 24E (≤4
diagnosis pointers per service line) and the 4-modifier line limit.
"""

from __future__ import annotations

from typing import Any

MAX_DIAGNOSIS_POINTERS = 4
MAX_MODIFIERS = 4


def validate_charge_enrichment(charges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return a list of ``{command_uuid, errors:[...]}`` for charges that
    violate a rule. An empty list means every charge is valid.

    Rules (order of error codes is stable for test/UI consumption):
      * ``at_least_one_pointer`` — a charge must point to ≥1 diagnosis.
      * ``too_many_pointers``    — ≤ ``MAX_DIAGNOSIS_POINTERS`` pointers.
      * ``too_many_modifiers``   — ≤ ``MAX_MODIFIERS`` modifiers.
    """
    failures: list[dict[str, Any]] = []
    for charge in charges:
        errors: list[str] = []
        pointers = charge.get("diagnosis_pointers") or []
        modifiers = charge.get("modifiers") or []
        if not pointers:
            errors.append("at_least_one_pointer")
        if len(pointers) > MAX_DIAGNOSIS_POINTERS:
            errors.append("too_many_pointers")
        if len(modifiers) > MAX_MODIFIERS:
            errors.append("too_many_modifiers")
        if errors:
            # Empty-string fallback is intentional; upstream callers always supply command_uuid.
            failures.append({"command_uuid": charge.get("command_uuid", ""), "errors": errors})
    return failures
