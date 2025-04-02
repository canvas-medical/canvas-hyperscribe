from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.imaging_order import ImagingOrder
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = ImagingOrder
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ImagingOrder
    result = tested.schema_key()
    expected = "imagingOrder"
    assert result == expected


def test_staged_command_extract():
    tested = ImagingOrder
    tests = [
        ({}, None),
        ({
             "image": {"text": "theImaging"},
             "comment": "theComment",
             "priority": "thePriority",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(label="theImaging: theComment (priority: thePriority, related conditions: indication1/indication2/indication3)", code="",
                      uuid="")),
        ({
             "image": {"text": "theImaging"},
             "comment": "theComment",
             "priority": "thePriority",
             "indications": [],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(label="theImaging: theComment (priority: thePriority, related conditions: n/a)", code="", uuid="")),
        ({
             "image": {"text": "theImaging"},
             "comment": "theComment",
             "priority": "",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(label="theImaging: theComment (priority: n/a, related conditions: indication1/indication2/indication3)", code="", uuid="")),
        ({
             "image": {"text": "theImaging"},
             "comment": "",
             "priority": "thePriority",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, CodedItem(label="theImaging: n/a (priority: thePriority, related conditions: indication1/indication2/indication3)", code="", uuid="")),
        ({
             "image": {"text": ""},
             "comment": "theComment",
             "priority": "thePriority",
             "indications": [
                 {"text": "indication1"},
                 {"text": "indication2"},
                 {"text": "indication3"},
             ],
             "additional_details": "additionalOrderDetails"
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
