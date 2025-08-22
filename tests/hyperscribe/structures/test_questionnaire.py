from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.questionnaire import Questionnaire
from hyperscribe.structures.response import Response
from tests.helper import is_namedtuple


def test_class():
    tested = Questionnaire
    fields = {"dbid": int, "name": str, "questions": list[Question]}
    assert is_namedtuple(tested, fields)


def test_to_json():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True, comment="theComment1"),
        Response(dbid=143, value="theResponse2", selected=False, comment="theComment2"),
        Response(dbid=144, value="theResponse3", selected=True, comment="theComment3"),
    ]
    tested = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=responses[:2],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=responses[2:3],
            ),
        ],
    )
    result = tested.to_json()
    expected = {
        "dbid": 123,
        "name": "theQuestionnaire",
        "questions": [
            {
                "dbid": 234,
                "label": "theQuestion1",
                "responses": [
                    {"dbid": 142, "selected": True, "value": "theResponse1", "comment": "theComment1"},
                    {"dbid": 143, "selected": False, "value": "theResponse2", "comment": "theComment2"},
                ],
                "skipped": False,
                "type": "SING",
            },
            {
                "dbid": 345,
                "label": "theQuestion2",
                "responses": [{"dbid": 144, "selected": True, "value": "theResponse3", "comment": "theComment3"}],
                "skipped": True,
                "type": "TXT",
            },
        ],
    }
    assert result == expected


def test_for_llm_limited_to():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True, comment="theComment1"),
        Response(dbid=143, value="theResponse2", selected=False, comment="theComment2"),
        Response(dbid=144, value="theResponse3", selected=True, comment="theComment3"),
        Response(dbid=145, value=444, selected=True, comment="theComment4"),
        Response(dbid=146, value="theResponse5", selected=True, comment="theComment5"),
        Response(dbid=147, value="theResponse6", selected=True, comment="theComment6"),
        Response(dbid=148, value="theResponse7", selected=False, comment="theComment7"),
    ]
    tested = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=responses[:2],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=responses[2:3],
            ),
            Question(
                dbid=369,
                label="theQuestion3",
                type=QuestionType.TYPE_INTEGER,
                skipped=True,
                responses=responses[3:4],
            ),
            Question(
                dbid=371,
                label="theQuestion4",
                type=QuestionType.TYPE_CHECKBOX,
                skipped=False,
                responses=responses[4:7],
            ),
        ],
    )
    expected = [
        {
            "question": "theQuestion1",
            "questionId": 234,
            "questionType": "single choice",
            "responses": [
                {"responseId": 142, "selected": True, "value": "theResponse1"},
                {"responseId": 143, "selected": False, "value": "theResponse2"},
            ],
            "skipped": False,
        },
        {
            "question": "theQuestion2",
            "questionId": 345,
            "questionType": "free text",
            "responses": [{"responseId": 144, "selected": True, "value": "theResponse3"}],
            "skipped": True,
        },
        {
            "question": "theQuestion3",
            "questionId": 369,
            "questionType": "integer",
            "responses": [{"responseId": 145, "selected": True, "value": 444}],
            "skipped": True,
        },
        {
            "question": "theQuestion4",
            "questionId": 371,
            "questionType": "multiple choice",
            "responses": [
                {
                    "responseId": 146,
                    "selected": True,
                    "value": "theResponse5",
                    "comment": "theComment5",
                    "description": "add in the comment key any relevant information expanding the answer",
                },
                {
                    "responseId": 147,
                    "selected": True,
                    "value": "theResponse6",
                    "comment": "theComment6",
                    "description": "add in the comment key any relevant information expanding the answer",
                },
                {
                    "responseId": 148,
                    "selected": False,
                    "value": "theResponse7",
                    "comment": "theComment7",
                    "description": "add in the comment key any relevant information expanding the answer",
                },
            ],
            "skipped": False,
        },
    ]
    result = tested.for_llm_limited_to(True, [234, 345, 369, 371])
    assert result == expected
    result = tested.for_llm_limited_to(True, [234, 369, 371])
    assert result == [expected[i] for i in [0, 2, 3]]
    #
    expected = [
        {
            "question": "theQuestion1",
            "questionId": 234,
            "questionType": "single choice",
            "responses": [
                {"responseId": 142, "selected": True, "value": "theResponse1"},
                {"responseId": 143, "selected": False, "value": "theResponse2"},
            ],
        },
        {
            "question": "theQuestion2",
            "questionId": 345,
            "questionType": "free text",
            "responses": [{"responseId": 144, "selected": True, "value": "theResponse3"}],
        },
        {
            "question": "theQuestion3",
            "questionId": 369,
            "questionType": "integer",
            "responses": [{"responseId": 145, "selected": True, "value": 444}],
        },
        {
            "question": "theQuestion4",
            "questionId": 371,
            "questionType": "multiple choice",
            "responses": [
                {
                    "responseId": 146,
                    "selected": True,
                    "value": "theResponse5",
                    "comment": "theComment5",
                    "description": "add in the comment key any relevant information expanding the answer",
                },
                {
                    "responseId": 147,
                    "selected": True,
                    "value": "theResponse6",
                    "comment": "theComment6",
                    "description": "add in the comment key any relevant information expanding the answer",
                },
                {
                    "responseId": 148,
                    "selected": False,
                    "value": "theResponse7",
                    "comment": "theComment7",
                    "description": "add in the comment key any relevant information expanding the answer",
                },
            ],
        },
    ]
    result = tested.for_llm_limited_to(False, [234, 345, 369, 371])
    assert result == expected
    result = tested.for_llm_limited_to(False, [234, 369, 371])
    assert result == [expected[i] for i in [0, 2, 3]]


def test_used_questions():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True, comment="theComment1"),
        Response(dbid=143, value="theResponse2", selected=False, comment="theComment2"),
        Response(dbid=144, value="theResponse3", selected=True, comment="theComment3"),
        Response(dbid=145, value=444, selected=True, comment="theComment4"),
        Response(dbid=146, value="theResponse5", selected=True, comment="theComment5"),
        Response(dbid=147, value="theResponse6", selected=True, comment="theComment6"),
        Response(dbid=148, value="theResponse7", selected=False, comment="theComment7"),
    ]
    tested = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=responses[:2],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=responses[2:3],
            ),
            Question(
                dbid=369,
                label="theQuestion3",
                type=QuestionType.TYPE_INTEGER,
                skipped=True,
                responses=responses[3:4],
            ),
            Question(
                dbid=371,
                label="theQuestion4",
                type=QuestionType.TYPE_CHECKBOX,
                skipped=False,
                responses=responses[4:7],
            ),
        ],
    )
    result = tested.used_questions()
    expected = [
        {
            "question": "theQuestion1",
            "questionId": 234,
            "usedInTranscript": False,
        },
        {
            "question": "theQuestion2",
            "questionId": 345,
            "usedInTranscript": False,
        },
        {
            "question": "theQuestion3",
            "questionId": 369,
            "usedInTranscript": False,
        },
        {
            "question": "theQuestion4",
            "questionId": 371,
            "usedInTranscript": False,
        },
    ]
    assert result == expected


def test_update_from_llm_with():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True, comment="theComment1"),
        Response(dbid=143, value="theResponse2", selected=False, comment="theComment2"),
        Response(dbid=144, value="theResponse3", selected=True, comment="theComment3"),
        Response(dbid=145, value=444, selected=True, comment="theComment4"),
        Response(dbid=146, value="theResponse5", selected=True, comment="theComment5"),
        Response(dbid=147, value="theResponse6", selected=True, comment="theComment6"),
        Response(dbid=148, value="theResponse7", selected=False, comment="theComment7"),
    ]
    tested = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=responses[:2],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=responses[2:3],
            ),
            Question(
                dbid=369,
                label="theQuestion3",
                type=QuestionType.TYPE_INTEGER,
                skipped=True,
                responses=responses[3:4],
            ),
            Question(
                dbid=371,
                label="theQuestion4",
                type=QuestionType.TYPE_CHECKBOX,
                skipped=False,
                responses=responses[4:7],
            ),
        ],
    )

    data = [
        {
            "question": "theQuestion1",
            "questionId": 234,
            "questionType": "single choice",
            "responses": [
                {"responseId": 142, "selected": False, "value": "theResponse1"},
                {"responseId": 143, "selected": True, "value": "theResponse2"},
            ],
            "skipped": False,
        },
        {
            "question": "theQuestion3",
            "questionId": 369,
            "questionType": "integer",
            "responses": [{"responseId": 145, "selected": True, "value": 789}],
            "skipped": False,
        },
    ]
    result = tested.update_from_llm_with(data)
    expected = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=[
                    Response(dbid=142, value="theResponse1", selected=False, comment=None),
                    Response(dbid=143, value="theResponse2", selected=True, comment=None),
                ],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=responses[2:3],
            ),
            Question(
                dbid=369,
                label="theQuestion3",
                type=QuestionType.TYPE_INTEGER,
                skipped=False,
                responses=[Response(dbid=145, value=789, selected=True, comment=None)],
            ),
            Question(
                dbid=371,
                label="theQuestion4",
                type=QuestionType.TYPE_CHECKBOX,
                skipped=False,
                responses=responses[4:7],
            ),
        ],
    )
    assert result == expected


def test_load_from():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True, comment="theComment1"),
        Response(dbid=143, value="theResponse2", selected=False, comment="theComment2"),
        Response(dbid=144, value="theResponse3", selected=True, comment="theComment3"),
    ]
    tested = Questionnaire
    result = tested.load_from(
        {
            "dbid": 123,
            "name": "theQuestionnaire",
            "questions": [
                {
                    "dbid": 234,
                    "label": "theQuestion1",
                    "responses": [
                        {"dbid": 142, "selected": True, "value": "theResponse1", "comment": "theComment1"},
                        {"dbid": 143, "selected": False, "value": "theResponse2", "comment": "theComment2"},
                    ],
                    "skipped": False,
                    "type": "SING",
                },
                {
                    "dbid": 345,
                    "label": "theQuestion2",
                    "responses": [{"dbid": 144, "selected": True, "value": "theResponse3", "comment": "theComment3"}],
                    "skipped": True,
                    "type": "TXT",
                },
            ],
        },
    )
    expected = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=responses[:2],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=responses[2:3],
            ),
        ],
    )
    assert result == expected
