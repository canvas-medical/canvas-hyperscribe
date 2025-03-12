from typing import ForwardRef

from hyperscribe.handlers.structures.line import Line
from tests.helper import is_namedtuple


def test_class():
    tested = Line
    fields = {
        "speaker": str,
        "text": str,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json():
    tested = Line
    result = tested.load_from_json([
        {"speaker": "theSpeaker1", "text": "theText1"},
        {"speaker": "theSpeaker2", "text": "theText2"},
        {},
        {"speaker": "theSpeaker3", "text": "theText3"},
    ])
    expected = [
        Line(speaker="theSpeaker1", text="theText1"),
        Line(speaker="theSpeaker2", text="theText2"),
        Line(speaker="", text=""),
        Line(speaker="theSpeaker3", text="theText3"),
    ]
    assert result == expected


def test_to_json():
    tested = Line(speaker="theSpeaker", text="theText")
    result = tested.to_json()
    expected = {
        "speaker": "theSpeaker",
        "text": "theText",
    }
    assert expected == result
