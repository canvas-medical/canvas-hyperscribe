from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.lab_order import LabOrder
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = LabOrder
    assert issubclass(tested, Base)


def test_schema_key():
    tested = LabOrder
    result = tested.schema_key()
    expected = "labOrder"
    assert result == expected


def test_staged_command_extract():
    tested = LabOrder
    tests = [
        ({}, None),
        ({
             "tests": [
                 {"text": "test1"},
                 {"text": "test2"},
                 {"text": "test3"},
             ],
             "comment": "theComment",
             "diagnosis": [
                 {"text": "diagnose1"},
                 {"text": "diagnose2"},
             ],
             "fasting_status": True,
         }, CodedItem(label="test1/test2/test3: theComment (fasting: yes, diagnosis: diagnose1/diagnose2)", code="", uuid="")),
        ({
             "tests": [],
             "comment": "theComment",
             "diagnosis": [
                 {"text": "diagnose1"},
                 {"text": "diagnose2"},
             ],
             "fasting_status": True,
         }, None),
        ({
             "tests": [{"text": "test1"}],
             "comment": "",
             "diagnosis": [{"text": "diagnose1"}],
             "fasting_status": False,
         }, CodedItem(label="test1: n/a (fasting: no, diagnosis: diagnose1)", code="", uuid="")),
        ({
             "tests": [{"text": "test1"}],
             "comment": "",
             "diagnosis": [],
             "fasting_status": False,
         }, CodedItem(label="test1: n/a (fasting: no, diagnosis: n/a)", code="", uuid="")),
        ({
             "tests": [{"text": "test1"}],
             "comment": "",
             "diagnosis": [{"text": "diagnose1"}],
         }, CodedItem(label="test1: n/a (fasting: n/a, diagnosis: diagnose1)", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
