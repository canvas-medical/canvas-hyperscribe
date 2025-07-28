from hyperscribe.structures.charge_description import ChargeDescription
from tests.helper import is_namedtuple


def test_class():
    tested = ChargeDescription
    fields = {"full_name": str, "short_name": str, "cpt_code": str}
    assert is_namedtuple(tested, fields)


def test_to_dict():
    tested = ChargeDescription(full_name="theFullName", short_name="theShortName", cpt_code="theCPTCode")
    result = tested.to_dict()
    expected = {"fullName": "theFullName", "shortName": "theShortName", "cptCode": "theCPTCode"}
    assert result == expected


def test_load_from_json():
    tested = ChargeDescription

    result = tested.load_from_json({"fullName": "theFullName", "shortName": "theShortName", "cptCode": "theCPTCode"})
    expected = ChargeDescription(full_name="theFullName", short_name="theShortName", cpt_code="theCPTCode")
    assert result == expected

    result = tested.load_from_json({"full_name": "theFullName", "short_name": "theShortName", "cpt_code": "theCPTCode"})
    expected = ChargeDescription(full_name="theFullName", short_name="theShortName", cpt_code="theCPTCode")
    assert result == expected
