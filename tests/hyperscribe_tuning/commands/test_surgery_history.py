from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.surgery_history import SurgeryHistory
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = SurgeryHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = SurgeryHistory
    result = tested.schema_key()
    expected = "surgicalHistory"
    assert result == expected


def test_staged_command_extract():
    tested = SurgeryHistory
    tests = [
        ({}, None),
        ({
             "comment": "theComment",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: theComment (on: theDate)", code="40653006", uuid="")),
        ({
             "comment": "theComment",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "",
                 "value": 40653006,
             }
         }, None),
        ({
             "comment": "theComment",
             "approximate_date": {"date": ""},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: theComment (on: n/a)", code="40653006", uuid="")),
        ({
             "comment": "",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: n/a (on: theDate)", code="40653006", uuid="")),
        ({
             "comment": "theComment",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: theComment (on: theDate)", code="40653006", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
