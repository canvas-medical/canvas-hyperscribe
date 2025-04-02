from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.reason_for_visit import ReasonForVisit
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = ReasonForVisit
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ReasonForVisit
    result = tested.schema_key()
    expected = "reasonForVisit"
    assert result == expected


def test_staged_command_extract():
    tested = ReasonForVisit
    tests = [
        ({}, None),
        ({
             "coding": {"text": "theStructuredRfV"},
             "comment": "theComment"
         }, CodedItem(label="theStructuredRfV", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "comment": "theComment"
         }, CodedItem(label="theComment", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "comment": ""
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
