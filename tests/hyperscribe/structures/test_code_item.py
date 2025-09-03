from unittest.mock import patch, call

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


@patch.object(CodedItem, "load_from_json")
def test_load_from_json_list(load_from_json):
    def reset_mocks():
        load_from_json.reset_mock()

    tested = CodedItem
    load_from_json.side_effect = ["item1", "item2", "item3"]
    result = tested.load_from_json_list([{"data": "value1"}, {"data": "value2"}, {"data": "value3"}])
    expected = ["item1", "item2", "item3"]
    assert result == expected

    calls = [
        call({"data": "value1"}),
        call({"data": "value2"}),
        call({"data": "value3"}),
    ]
    assert load_from_json.mock_calls == calls
    reset_mocks()
