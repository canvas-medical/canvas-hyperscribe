from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.resolve_condition import ResolveCondition
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = ResolveCondition
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ResolveCondition
    result = tested.schema_key()
    expected = "resolveCondition"
    assert result == expected


def test_staged_command_extract():
    tested = ResolveCondition
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
         }, CodedItem(label="theCondition: ", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
