from hyperscribe.structures.question_used import QuestionUsed
from tests.helper import is_namedtuple


def test_class():
    tested = QuestionUsed
    fields = {
        "dbid": int,
        "label": str,
        "used": bool,
    }
    assert is_namedtuple(tested, fields)


def test_for_llm():
    tested = QuestionUsed(
        dbid=123,
        label="theQuestion",
        used=False,
    )
    result = tested.for_llm()
    expected = {
        "questionId": 123,
        "question": "theQuestion",
        "usedInTranscript": False,
    }
    assert result == expected


def test_load_from_llm():
    tested = QuestionUsed
    #
    result = tested.load_from_llm([])
    assert result == []
    #
    result = tested.load_from_llm(
        [
            {
                "questionId": 123,
                "question": "theQuestion123",
                "usedInTranscript": False,
            },
            {
                "questionId": 147,
                "question": "theQuestion147",
                "usedInTranscript": True,
            },
            {
                "questionId": 135,
                "question": "theQuestion135",
                "usedInTranscript": True,
            },
        ]
    )
    expected = [
        QuestionUsed(dbid=123, label="theQuestion123", used=False),
        QuestionUsed(dbid=147, label="theQuestion147", used=True),
        QuestionUsed(dbid=135, label="theQuestion135", used=True),
    ]
    assert result == expected
