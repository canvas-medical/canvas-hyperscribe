from hyperscribe.structures.line import Line
from tests.helper import is_namedtuple


def test_class():
    tested = Line
    fields = {
        "speaker": str,
        "text": str,
        "start": float,
        "end": float,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json():
    tested = Line
    result = tested.load_from_json(
        [
            {"speaker": "theSpeaker1", "text": "theText1", "start": 0.0, "end": 1.3},
            {"speaker": "theSpeaker2", "text": "theText2", "start": 1.3, "end": 2.5},
            {},
            {"speaker": "theSpeaker3", "text": "theText3", "start": 3.6, "end": 4.7},
        ],
    )
    expected = [
        Line(speaker="theSpeaker1", text="theText1", start=0.0, end=1.3),
        Line(speaker="theSpeaker2", text="theText2", start=1.3, end=2.5),
        Line(speaker="", text="", start=0.0, end=0.0),
        Line(speaker="theSpeaker3", text="theText3", start=3.6, end=4.7),
    ]
    assert result == expected


def test_to_json():
    tested = Line(speaker="theSpeaker", text="theText", start=2.5, end=3.6)
    result = tested.to_json()
    expected = {
        "speaker": "theSpeaker",
        "text": "theText",
        "start": 2.5,
        "end": 3.6,
    }
    assert expected == result


def test_tail_of():
    tested = Line

    # empty exchange
    result = tested.tail_of([], 100)
    expected = []
    assert result == expected

    # exchange
    exchange = [
        Line(speaker="theSpeaker1", text=" ".join([f"word{i:02d}" for i in range(37)]), start=0.0, end=1.3),
        Line(speaker="theSpeaker2", text=" ".join([f"word{i:02d}" for i in range(37)]), start=1.3, end=2.5),
        Line(speaker="theSpeaker1", text=" ".join([f"word{i:02d}" for i in range(37)]), start=2.5, end=3.6),
    ]
    result = tested.tail_of(exchange, 100)
    expected = [
        Line(
            speaker="theSpeaker1",
            text=" ".join([f"word{i:02d}" for i in range((37 * 3 - 100), 37)]),
            start=0.0,
            end=1.3,
        ),
        Line(
            speaker="theSpeaker2",
            text=" ".join([f"word{i:02d}" for i in range(37)]),
            start=1.3,
            end=2.5,
        ),
        Line(
            speaker="theSpeaker1",
            text=" ".join([f"word{i:02d}" for i in range(37)]),
            start=2.5,
            end=3.6,
        ),
    ]
    assert result == expected
    #
    result = tested.tail_of(exchange, 33)
    expected = [
        Line(
            speaker="theSpeaker1",
            text=" ".join([f"word{i:02d}" for i in range((37 - 33), 37)]),
            start=2.5,
            end=3.6,
        )
    ]
    assert result == expected
    #
    result = tested.tail_of(exchange, 330)
    assert result == exchange
