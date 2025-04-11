from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.perform import Perform
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Perform
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Perform
    result = tested.schema_key()
    expected = "perform"
    assert result == expected


def test_staged_command_extract():
    tested = Perform
    tests = [
        ({}, None),
        ({
             "notes": "theNotes",
             "perform": {"text": "theProcedure"}
         }, CodedItem(label="theProcedure: theNotes", code="", uuid="")),
        ({
             "notes": "theNotes",
             "perform": {"text": ""}
         }, None),
        ({
             "notes": "",
             "perform": {"text": "theProcedure"}
         }, CodedItem(label="theProcedure: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
