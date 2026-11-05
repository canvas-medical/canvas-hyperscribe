"""Shared config + parsing for the Alert Facility flag.

Alert Facility is gated per command type via the ``AlertFacilityCommands`` secret,
a comma-separated list of ``command_type`` names. A command shows the toggle (and
records / displays the flag) only when its ``command_type`` is in that list; an
empty/unset list turns the feature off everywhere.

This module is the single source of truth for the supported command types, their
committed ``schema_key`` mapping, their per-type default, and the secret parser —
shared by the API views (``scribe_view``, ``session_view``) so backend and frontend
stay consistent.
"""

from __future__ import annotations

# Frontend/parser ``command_type`` (snake_case) -> committed ``Command.schema_key`` (camelCase).
SCHEMA_KEY_BY_COMMAND_TYPE: dict[str, str] = {
    "prescribe": "prescribe",
    "adjust_prescription": "adjustPrescription",
    "refill": "refill",
    "medication_statement": "medicationStatement",
    "stop_medication": "stopMedication",
}

# Reverse lookup for the committed ``/note-commands`` cards, which carry schema_key.
COMMAND_TYPE_BY_SCHEMA_KEY: dict[str, str] = {v: k for k, v in SCHEMA_KEY_BY_COMMAND_TYPE.items()}

# Per-command-type default position when no explicit value exists. Prescribe and
# adjust prescription default on; the rest default off.
DEFAULT_ON_BY_COMMAND_TYPE: dict[str, bool] = {
    "prescribe": True,
    "adjust_prescription": True,
    "refill": False,
    "medication_statement": False,
    "stop_medication": False,
}

SUPPORTED_COMMAND_TYPES: frozenset[str] = frozenset(SCHEMA_KEY_BY_COMMAND_TYPE)


def parse_alert_facility_commands(raw: str | None) -> set[str]:
    """Parse the ``AlertFacilityCommands`` secret (comma-separated command types)
    into a normalized set of allowed command types. Blank entries and unknown
    names (typos, unsupported commands) are dropped."""
    return {entry.strip().lower() for entry in (raw or "").split(",") if entry.strip()} & SUPPORTED_COMMAND_TYPES
