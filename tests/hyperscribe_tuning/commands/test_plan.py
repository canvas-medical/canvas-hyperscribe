from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.plan import Plan
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Plan
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Plan
    result = tested.schema_key()
    expected = "plan"
    assert result == expected


def test_staged_command_extract():
    tested = Plan
    tests = [
        ({}, None),
        ({"narrative": "theNarrative"}, CodedItem(label="theNarrative", code="", uuid="")),
        ({"narrative": ""}, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
