from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = HistoryOfPresentIllness
    assert issubclass(tested, Base)


def test_schema_key():
    tested = HistoryOfPresentIllness
    result = tested.schema_key()
    expected = "hpi"
    assert result == expected


def test_staged_command_extract():
    tested = HistoryOfPresentIllness
    tests = [
        ({}, None),
        ({"narrative": "theNarrative"}, CodedItem(label="theNarrative", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
