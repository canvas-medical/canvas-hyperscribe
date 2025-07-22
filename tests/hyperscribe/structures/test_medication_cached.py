from hyperscribe.structures.medication_cached import MedicationCached
from tests.helper import is_namedtuple


def test_class():
    tested = MedicationCached
    fields = {
        "uuid": str,
        "label": str,
        "code_rx_norm": str,
        "code_fdb": str,
        "national_drug_code": str,
        "potency_unit_code": str,
    }
    assert is_namedtuple(tested, fields)


def test_to_dict():
    tested = MedicationCached(
        uuid="theUuid",
        label="theLabel",
        code_rx_norm="theCodeRxNorm",
        code_fdb="theCodeFdb",
        national_drug_code="theNationalDrugCode",
        potency_unit_code="thePotencyUnitCode",
    )
    result = tested.to_dict()
    expected = {
        "uuid": "theUuid",
        "label": "theLabel",
        "codeRxNorm": "theCodeRxNorm",
        "codeFdb": "theCodeFdb",
        "nationalDrugCode": "theNationalDrugCode",
        "potencyUnitCode": "thePotencyUnitCode",
    }
    assert result == expected


def test_load_from_json():
    tested = MedicationCached
    # old version
    result = tested.load_from_json({"uuid": "theUuid", "label": "theLabel", "code": "theCode"})
    expected = MedicationCached(
        uuid="theUuid",
        label="theLabel",
        code_rx_norm="theCode",
        code_fdb="",
        national_drug_code="",
        potency_unit_code="",
    )
    assert result == expected
    # new version
    result = tested.load_from_json(
        {
            "uuid": "theUuid",
            "label": "theLabel",
            "codeRxNorm": "theCodeRxNorm",
            "codeFdb": "theCodeFdb",
            "nationalDrugCode": "theNationalDrugCode",
            "potencyUnitCode": "thePotencyUnitCode",
        },
    )
    expected = MedicationCached(
        uuid="theUuid",
        label="theLabel",
        code_rx_norm="theCodeRxNorm",
        code_fdb="theCodeFdb",
        national_drug_code="theNationalDrugCode",
        potency_unit_code="thePotencyUnitCode",
    )
    assert result == expected
