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


def test_load_from_csv():
    tested = Line

    # empty csv list
    result = tested.load_from_csv([])
    expected = []
    assert result == expected

    # csv list with header and data
    csv_list = [
        "speaker,text,start,end",
        "theSpeaker1,theText1,0.0,1.3",
        "theSpeaker2,theText2,1.3,2.5",
        '"theSpeaker3","text with, comma",3.6,4.7',
    ]
    result = tested.load_from_csv(csv_list)
    expected = [
        Line(speaker="theSpeaker1", text="theText1", start=0.0, end=1.3),
        Line(speaker="theSpeaker2", text="theText2", start=1.3, end=2.5),
        Line(speaker="theSpeaker3", text="text with, comma", start=3.6, end=4.7),
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


def test_list_to_csv():
    tested = Line

    # empty list
    result = tested.list_to_csv([])
    expected = "speaker,text,start,end"
    assert result == expected

    # list with lines
    lines = [
        Line(speaker="theSpeaker1", text="theText1", start=0.0, end=1.3),
        Line(speaker="theSpeaker2", text="text with, comma", start=1.3, end=2.5),
        Line(speaker="theSpeaker3", text='text with "quotes"', start=2.5, end=3.6),
    ]
    result = tested.list_to_csv(lines)
    expected = (
        "speaker,text,start,end\n"
        "theSpeaker1,theText1,0.0,1.3\n"
        'theSpeaker2,"text with, comma",1.3,2.5\n'
        'theSpeaker3,"text with ""quotes""",2.5,3.6'
    )
    assert result == expected


def test_to_csv_description():
    tested = Line
    result = tested.to_csv_description()
    expected = (
        "speaker,text,start,end\n"
        "Patient/Clinician/Nurse/Parent...,the verbatim transcription as reported in the transcription,"
        "the start as reported in the transcription,the end as reported in the transcription"
    )
    assert result == expected
