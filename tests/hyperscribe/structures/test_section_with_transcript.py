from hyperscribe.structures.line import Line
from hyperscribe.structures.section_with_transcript import SectionWithTranscript
from tests.helper import is_namedtuple


def test_class():
    tested = SectionWithTranscript
    fields = {
        "section": str,
        "transcript": list[Line],
    }
    assert is_namedtuple(tested, fields)


def test_load_from():
    tested = SectionWithTranscript
    #
    result = tested.load_from([])
    assert result == []

    #
    result = tested.load_from(
        [
            {
                "section": "theSection1",
                "transcript": [
                    {"speaker": "theSpeaker1", "text": "theText1"},
                    {"speaker": "theSpeaker2", "text": "theText2"},
                    {},
                    {"speaker": "theSpeaker3", "text": "theText3"},
                ],
            },
            {
                "section": "theSection2",
                "transcript": [],
            },
            {
                "section": "theSection3",
                "transcript": [
                    {"speaker": "theSpeaker4", "text": "theText4"},
                    {"speaker": "theSpeaker5", "text": "theText5"},
                ],
            },
        ],
    )
    expected = [
        SectionWithTranscript(
            section="theSection1",
            transcript=[
                Line(speaker="theSpeaker1", text="theText1"),
                Line(speaker="theSpeaker2", text="theText2"),
                Line(speaker="", text=""),
                Line(speaker="theSpeaker3", text="theText3"),
            ],
        ),
        SectionWithTranscript(
            section="theSection2",
            transcript=[],
        ),
        SectionWithTranscript(
            section="theSection3",
            transcript=[
                Line(speaker="theSpeaker4", text="theText4"),
                Line(speaker="theSpeaker5", text="theText5"),
            ],
        ),
    ]
    assert result == expected
