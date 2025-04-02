from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.medication import Medication
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Medication
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Medication
    result = tested.schema_key()
    expected = "medicationStatement"
    assert result == expected


def test_staged_command_extract():
    tested = Medication
    tests = [
        ({}, None),
        ({
             "sig": "theSig",
             "medication": {"text": "theMedication"}
         }, CodedItem(label="theMedication: theSig", code="", uuid="")),
        ({
             "sig": "theSig",
             "medication": {"text": ""}
         }, None),
        ({
             "sig": "",
             "medication": {"text": "theMedication"}
         }, CodedItem(label="theMedication: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
