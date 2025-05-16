from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.stop_medication import StopMedication
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = StopMedication
    assert issubclass(tested, Base)


def test_schema_key():
    tested = StopMedication
    result = tested.schema_key()
    expected = "stopMedication"
    assert result == expected


def test_staged_command_extract():
    tested = StopMedication
    tests = [
        ({}, None),
        ({
             "medication": {"text": "theMedication"},
             "rationale": "theRationale",
         }, CodedItem(label="theMedication: theRationale", code="", uuid="")),
        ({
             "medication": {"text": ""},
             "rationale": "theRationale",
         }, None),
        ({
             "medication": {"text": "theMedication"},
             "rationale": "",
         }, CodedItem(label="theMedication: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
