from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.instruct import Instruct
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Instruct
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Instruct
    result = tested.schema_key()
    expected = "instruct"
    assert result == expected


def test_staged_command_extract():
    tested = Instruct
    tests = [
        ({}, None),
        ({
             "instruct": {"text": "theInstruction"},
             "narrative": "theNarrative"
         }, CodedItem(label="theInstruction (theNarrative)", code="", uuid="")),
        ({
             "instruct": {"text": "theInstruction"},
             "narrative": ""
         }, CodedItem(label="theInstruction (n/a)", code="", uuid="")),
        ({
             "instruct": {"text": "", },
             "narrative": "theNarrative"
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
