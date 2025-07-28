from hyperscribe.structures.coded_item import CodedItem
from tests.helper import is_namedtuple


def test_class():
    tested = CodedItem
    fields = {"uuid": str, "label": str, "code": str}
    assert is_namedtuple(tested, fields)


def test_to_dict():
    tested = CodedItem(uuid="theUuid", label="theLabel", code="theCode")
    result = tested.to_dict()
    expected = {"uuid": "theUuid", "label": "theLabel", "code": "theCode"}
    assert result == expected


def test_load_from_json():
    tested = CodedItem
    result = tested.load_from_json({"uuid": "theUuid", "label": "theLabel", "code": "theCode"})
    expected = CodedItem(uuid="theUuid", label="theLabel", code="theCode")
    assert result == expected
