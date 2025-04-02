from hyperscribe_tuning.commands.assess import Assess
from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Assess
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Assess
    result = tested.schema_key()
    expected = "assess"
    assert result == expected


def test_staged_command_extract():
    tested = Assess
    tests = [
        ({}, None),
        ({
             "condition": {},
             "narrative": "better",
             "background": "theBackground",
         }, None),
        ({
             "condition": {
                 "text": "theCondition",
                 "annotations": ["theCode"],
             },
             "narrative": "theNarrative",
             "background": "theBackground",
         }, CodedItem(label="theCondition: theNarrative", code="", uuid="")),
        ({
             "condition": {
                 "text": "theCondition",
                 "annotations": ["theCode"],
             },
             "narrative": "",
             "background": "theBackground",
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
