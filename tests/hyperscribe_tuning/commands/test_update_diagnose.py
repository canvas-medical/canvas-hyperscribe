from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.update_diagnose import UpdateDiagnose
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = UpdateDiagnose
    assert issubclass(tested, Base)


def test_schema_key():
    tested = UpdateDiagnose
    result = tested.schema_key()
    expected = "updateDiagnosis"
    assert result == expected


def test_staged_command_extract():
    tested = UpdateDiagnose
    tests = [
        ({}, None),
        ({
             "condition": {"text": "theCondition"},
             "narrative": "theNarrative",
             "background": "theBackground",
             "new_condition": {"text": "theNewCondition"}
         }, CodedItem(label="theCondition to theNewCondition: theNarrative", code="", uuid="")),
        ({
             "condition": {"text": ""},
             "narrative": "theNarrative",
             "background": "theBackground",
             "new_condition": {"text": "theNewCondition"}
         }, None),
        ({
             "condition": {"text": "theCondition"},
             "narrative": "",
             "background": "theBackground",
             "new_condition": {"text": "theNewCondition"}
         }, CodedItem(label="theCondition to theNewCondition: n/a", code="", uuid="")),
        ({
             "condition": {"text": "theCondition"},
             "narrative": "theNarrative",
             "background": "theBackground",
             "new_condition": {"text": ""}
         }, CodedItem(label="theCondition to n/a: theNarrative", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
