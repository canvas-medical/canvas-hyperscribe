from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.family_history import FamilyHistory
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = FamilyHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = FamilyHistory
    result = tested.schema_key()
    expected = "familyHistory"
    assert result == expected


def test_staged_command_extract():
    tested = FamilyHistory
    tests = [
        ({}, None),
        ({
             "relative": {"text": "theRelative"},
             "family_history": {"text": "theFamilyHistory"}
         }, CodedItem(label="theRelative: theFamilyHistory", code="", uuid="")),
        ({
             "relative": {"text": "theRelative"},
             "family_history": {"text": ""}
         }, None),
        ({
             "relative": {"text": ""},
             "family_history": {"text": "theFamilyHistory"}
         }, None),

    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
