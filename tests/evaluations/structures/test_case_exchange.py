from evaluations.structures.case_exchange import CaseExchange
from tests.helper import is_dataclass


def test_class():
    tested = CaseExchange
    fields = {
        "speaker": "str",
        "text": "str",
        "chunk": "int",
    }
    assert is_dataclass(tested, fields)


def test_load_from_json():
    tested = CaseExchange
    result = tested.load_from_json([
        {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1},
        {"speaker": "theSpeaker2", "text": "theText2", "chunk": 2},
        {"speaker": "theSpeaker1", "text": "theText3", "chunk": 2},
    ])
    expected = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=1),
        CaseExchange(speaker="theSpeaker2", text="theText2", chunk=2),
        CaseExchange(speaker="theSpeaker1", text="theText3", chunk=2),
    ]
    assert result == expected


def test_load_from_json_default():
    tested = CaseExchange
    result = tested.load_from_json_default([
        {"speaker": "theSpeaker1", "text": "theText1"},
        {"speaker": "theSpeaker2", "text": "theText2"},
        {"speaker": "theSpeaker1", "text": "theText3", "chunk": 2},
    ], 7)
    expected = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=7),
        CaseExchange(speaker="theSpeaker2", text="theText2", chunk=7),
        CaseExchange(speaker="theSpeaker1", text="theText3", chunk=2),
    ]
    assert result == expected


def test_to_json():
    tested = CaseExchange(speaker="theSpeaker", text="theText", chunk=7)
    result = tested.to_json()
    expected = {"speaker": "theSpeaker", "text": "theText", "chunk": 7}
    assert result == expected
