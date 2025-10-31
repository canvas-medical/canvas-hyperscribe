from evaluations.structures.case_exchange import CaseExchange
from tests.helper import is_dataclass


def test_class():
    tested = CaseExchange
    fields = {
        "speaker": "str",
        "text": "str",
        "chunk": "int",
        "start": "float",
        "end": "float",
    }
    assert is_dataclass(tested, fields)


def test_load_from_json():
    tested = CaseExchange
    result = tested.load_from_json(
        [
            {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "start": 0.0, "end": 2.1},
            {"speaker": "theSpeaker2", "text": "theText2", "chunk": 2, "start": 2.1, "end": 4.8},
            {"speaker": "theSpeaker1", "text": "theText3", "chunk": 2, "start": 5.7, "end": 9.9},
        ],
    )
    expected = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=1, start=0.0, end=2.1),
        CaseExchange(speaker="theSpeaker2", text="theText2", chunk=2, start=2.1, end=4.8),
        CaseExchange(speaker="theSpeaker1", text="theText3", chunk=2, start=5.7, end=9.9),
    ]
    assert result == expected


def test_load_from_json_default():
    tested = CaseExchange
    result = tested.load_from_json_default(
        [
            {"speaker": "theSpeaker1", "text": "theText1", "start": 0.0, "end": 2.1},
            {"speaker": "theSpeaker2", "text": "theText2", "start": 2.1, "end": 4.8},
            {"speaker": "theSpeaker1", "text": "theText3", "chunk": 2, "start": 5.7, "end": 9.9},
        ],
        7,
    )
    expected = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=7, start=0.0, end=2.1),
        CaseExchange(speaker="theSpeaker2", text="theText2", chunk=7, start=2.1, end=4.8),
        CaseExchange(speaker="theSpeaker1", text="theText3", chunk=2, start=5.7, end=9.9),
    ]
    assert result == expected


def test_to_json():
    tested = CaseExchange(speaker="theSpeaker", text="theText", chunk=7, start=2.1, end=4.8)
    result = tested.to_json()
    expected = {"speaker": "theSpeaker", "text": "theText", "chunk": 7, "start": 2.1, "end": 4.8}
    assert result == expected
