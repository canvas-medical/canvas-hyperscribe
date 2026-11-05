from hyperscribe.scribe.commands._alert_facility import (
    COMMAND_TYPE_BY_SCHEMA_KEY,
    DEFAULT_ON_BY_COMMAND_TYPE,
    SCHEMA_KEY_BY_COMMAND_TYPE,
    SUPPORTED_COMMAND_TYPES,
    parse_alert_facility_commands,
)


def test_supported_command_types_match_maps() -> None:
    assert SUPPORTED_COMMAND_TYPES == frozenset(SCHEMA_KEY_BY_COMMAND_TYPE)
    assert SUPPORTED_COMMAND_TYPES == frozenset(DEFAULT_ON_BY_COMMAND_TYPE)
    # Reverse map is a true inverse.
    assert COMMAND_TYPE_BY_SCHEMA_KEY == {v: k for k, v in SCHEMA_KEY_BY_COMMAND_TYPE.items()}


def test_schema_key_mapping_is_camelcase() -> None:
    assert SCHEMA_KEY_BY_COMMAND_TYPE["adjust_prescription"] == "adjustPrescription"
    assert SCHEMA_KEY_BY_COMMAND_TYPE["medication_statement"] == "medicationStatement"
    assert SCHEMA_KEY_BY_COMMAND_TYPE["stop_medication"] == "stopMedication"


def test_parse_none_and_empty() -> None:
    assert parse_alert_facility_commands(None) == set()
    assert parse_alert_facility_commands("") == set()
    assert parse_alert_facility_commands("   ") == set()
    assert parse_alert_facility_commands(",, ,") == set()


def test_parse_splits_trims_and_lowercases() -> None:
    assert parse_alert_facility_commands(" Prescribe , REFILL ") == {"prescribe", "refill"}


def test_parse_drops_unknown_and_keeps_supported() -> None:
    assert parse_alert_facility_commands("prescribe,bogus,stop_medication") == {"prescribe", "stop_medication"}
    # A camelCase schema_key is NOT a valid command_type entry.
    assert parse_alert_facility_commands("adjustPrescription") == set()


def test_parse_all_supported() -> None:
    raw = "prescribe,adjust_prescription,refill,medication_statement,stop_medication"
    assert parse_alert_facility_commands(raw) == set(SUPPORTED_COMMAND_TYPES)
