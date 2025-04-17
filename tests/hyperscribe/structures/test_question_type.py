from hyperscribe.structures.question_type import QuestionType


def test_enum():
    tested = QuestionType
    assert len(tested) == 4
    assert tested.TYPE_TEXT.value == "TXT"
    assert tested.TYPE_INTEGER.value == "INT"
    assert tested.TYPE_RADIO.value == "SING"
    assert tested.TYPE_CHECKBOX.value == "MULT"


def test_llm_readable():
    tested = QuestionType
    result = tested.llm_readable()
    expected = {
        tested.TYPE_TEXT: "free text",
        tested.TYPE_INTEGER: "integer",
        tested.TYPE_RADIO: "single choice",
        tested.TYPE_CHECKBOX: "multiple choice",
    }
    assert result == expected
