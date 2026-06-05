from hyperscribe.scribe.charges.validation import (
    MAX_DIAGNOSIS_POINTERS,
    MAX_MODIFIERS,
    validate_charge_enrichment,
)


def _charge(command_uuid="c1", pointers=("M25.511",), modifiers=()):
    return {
        "command_uuid": command_uuid,
        "diagnosis_pointers": [{"command_uuid": f"d{i}", "icd10_code": p} for i, p in enumerate(pointers)],
        "modifiers": list(modifiers),
    }


def test_valid_charge_has_no_errors():
    assert validate_charge_enrichment([_charge()]) == []


def test_charge_with_zero_pointers_is_invalid():
    errors = validate_charge_enrichment([_charge(pointers=())])
    assert errors == [{"command_uuid": "c1", "errors": ["at_least_one_pointer"]}]


def test_charge_over_pointer_cap_is_invalid():
    pointers = tuple(f"A0{i}.0" for i in range(MAX_DIAGNOSIS_POINTERS + 1))
    errors = validate_charge_enrichment([_charge(pointers=pointers)])
    assert errors == [{"command_uuid": "c1", "errors": ["too_many_pointers"]}]


def test_charge_over_modifier_cap_is_invalid():
    modifiers = [str(n) for n in range(MAX_MODIFIERS + 1)]
    errors = validate_charge_enrichment([_charge(modifiers=modifiers)])
    assert errors == [{"command_uuid": "c1", "errors": ["too_many_modifiers"]}]


def test_multiple_violations_on_one_charge_are_all_reported():
    pointers = tuple(f"A0{i}.0" for i in range(MAX_DIAGNOSIS_POINTERS + 1))
    modifiers = [str(n) for n in range(MAX_MODIFIERS + 1)]
    errors = validate_charge_enrichment([_charge(pointers=pointers, modifiers=modifiers)])
    assert errors == [{"command_uuid": "c1", "errors": ["too_many_pointers", "too_many_modifiers"]}]


def test_each_invalid_charge_reported_separately():
    errors = validate_charge_enrichment([_charge("a", pointers=()), _charge("b")])
    assert errors == [{"command_uuid": "a", "errors": ["at_least_one_pointer"]}]
