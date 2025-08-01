from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.topical_exchange import TopicalExchange
from tests.helper import is_dataclass


def test_class():
    tested = TopicalExchange
    fields = {"speaker": "str", "text": "str", "chunk": "int", "topic": "int"}
    assert is_dataclass(tested, fields)

    assert issubclass(tested, CaseExchange)


def test_load_from_json():
    tested = TopicalExchange
    result = tested.load_from_json(
        [
            {"speaker": "theSpeaker1", "text": "theText1", "chunk": 1, "topic": 1},
            {"speaker": "theSpeaker2", "text": "theText2", "chunk": 2, "topic": 1},
            {"speaker": "theSpeaker1", "text": "theText3", "chunk": 2, "topic": 2},
        ],
    )
    expected = [
        TopicalExchange(speaker="theSpeaker1", text="theText1", chunk=1, topic=1),
        TopicalExchange(speaker="theSpeaker2", text="theText2", chunk=2, topic=1),
        TopicalExchange(speaker="theSpeaker1", text="theText3", chunk=2, topic=2),
    ]
    assert result == expected


def test_to_json():
    tested = TopicalExchange(speaker="theSpeaker", text="theText", chunk=7, topic=11)
    result = tested.to_json()
    expected = {"speaker": "theSpeaker", "text": "theText", "chunk": 7, "topic": 11}
    assert result == expected


def test_case_exchange_from():
    tested = TopicalExchange
    result = tested.case_exchange_from(
        [
            TopicalExchange(speaker="theSpeaker1", text="theText1", chunk=1, topic=1),
            TopicalExchange(speaker="theSpeaker2", text="theText2", chunk=2, topic=1),
            TopicalExchange(speaker="theSpeaker1", text="theText3", chunk=2, topic=2),
        ],
    )
    expected = [
        CaseExchange(speaker="theSpeaker1", text="theText1", chunk=1),
        CaseExchange(speaker="theSpeaker2", text="theText2", chunk=2),
        CaseExchange(speaker="theSpeaker1", text="theText3", chunk=2),
    ]
    assert result == expected
