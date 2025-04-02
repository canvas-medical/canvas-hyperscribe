from hyperscribe_tuning.commands.allergy import Allergy
from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Allergy
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Allergy
    result = tested.schema_key()
    expected = "allergy"
    assert result == expected


def test_staged_command_extract():
    tested = Allergy
    tests = [
        ({}, None),
        ({
             "allergy": {
                 "text": "theAllergy",
                 "value": 123456,
             },
         }, CodedItem(label="theAllergy", code="123456", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
