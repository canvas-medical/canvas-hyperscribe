from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.remove_allergy import RemoveAllergy
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = RemoveAllergy
    assert issubclass(tested, Base)


def test_schema_key():
    tested = RemoveAllergy
    result = tested.schema_key()
    expected = "removeAllergy"
    assert result == expected


def test_staged_command_extract():
    tested = RemoveAllergy
    tests = [
        ({}, None),
        ({
             "allergy": {"text": "theAllergy"},
             "narrative": "theNarrative",
         }
        , CodedItem(label="theAllergy: theNarrative", code="", uuid="")),
        ({
             "allergy": {"text": ""},
             "narrative": "theNarrative",
         }
        , None),
        ({
             "allergy": {"text": "theAllergy"},
             "narrative": "",
         }
        , CodedItem(label="theAllergy: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
