from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.questionnaire import Questionnaire
from hyperscribe.structures.response import Response
from tests.helper import is_namedtuple


def test_class():
    tested = Questionnaire
    fields = {
        "dbid": int,
        "name": str,
        "questions": list[Question],
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True),
        Response(dbid=143, value="theResponse2", selected=False),
        Response(dbid=144, value="theResponse3", selected=True),
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
        ]
    )
    result = tested.to_json()
    expected = {
        'dbid': 123,
        'name': 'theQuestionnaire',
        'questions': [
            {
                'dbid': 234,
                'label': 'theQuestion1',
                'responses': [
                    {'dbid': 142, 'selected': True, 'value': 'theResponse1'},
                    {'dbid': 143, 'selected': False, 'value': 'theResponse2'},
                ],
                'skipped': False,
                'type': 'SING',
            },
            {
                'dbid': 345,
                'label': 'theQuestion2',
                'responses': [{'dbid': 144, 'selected': True, 'value': 'theResponse3'}],
                'skipped': True,
                'type': 'TXT',
            },
        ],
    }
    assert result == expected


def test_for_llm():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True),
        Response(dbid=143, value="theResponse2", selected=False),
        Response(dbid=144, value="theResponse3", selected=True),
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
        ]
    )
    result = tested.for_llm(True)
    expected = [
        {
            'question': 'theQuestion1',
            'questionId': 234,
            'questionType': 'single choice',
            'responses': [
                {'responseId': 142, 'selected': True, 'value': 'theResponse1'},
                {'responseId': 143, 'selected': False, 'value': 'theResponse2'},
            ],
            'skipped': False,
        },
        {
            'question': 'theQuestion2',
            'questionId': 345,
            'questionType': 'free text',
            'responses': [
                {'responseId': 144, 'selected': True, 'value': 'theResponse3'},
            ],
            'skipped': True,
        },
    ]
    assert result == expected
    #
    result = tested.for_llm(False)
    expected = [
        {
            'question': 'theQuestion1',
            'questionId': 234,
            'questionType': 'single choice',
            'responses': [
                {'responseId': 142, 'selected': True, 'value': 'theResponse1'},
                {'responseId': 143, 'selected': False, 'value': 'theResponse2'},
            ],
        },
        {
            'question': 'theQuestion2',
            'questionId': 345,
            'questionType': 'free text',
            'responses': [
                {'responseId': 144, 'selected': True, 'value': 'theResponse3'},
            ],
        },
    ]
    assert result == expected


def test_load_from():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True),
        Response(dbid=143, value="theResponse2", selected=False),
        Response(dbid=144, value="theResponse3", selected=True),
    ]
    tested = Questionnaire
    result = tested.load_from({
        'dbid': 123,
        'name': 'theQuestionnaire',
        'questions': [
            {
                'dbid': 234,
                'label': 'theQuestion1',
                'responses': [
                    {'dbid': 142, 'selected': True, 'value': 'theResponse1'},
                    {'dbid': 143, 'selected': False, 'value': 'theResponse2'},
                ],
                'skipped': False,
                'type': 'SING',
            },
            {
                'dbid': 345,
                'label': 'theQuestion2',
                'responses': [{'dbid': 144, 'selected': True, 'value': 'theResponse3'}],
                'skipped': True,
                'type': 'TXT',
            },
        ],
    })
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
        ]
    )
    assert result == expected


def test_load_from_llm():
    responses = [
        Response(dbid=142, value="theResponse1", selected=True),
        Response(dbid=143, value="theResponse2", selected=False),
        Response(dbid=144, value="theResponse3", selected=True),
    ]
    tested = Questionnaire
    data = [
        {
            'question': 'theQuestion1',
            'questionId': 234,
            'questionType': 'single choice',
            'responses': [
                {'responseId': 142, 'selected': True, 'value': 'theResponse1'},
                {'responseId': 143, 'selected': False, 'value': 'theResponse2'},
            ],
            'skipped': False,
        },
        {
            'question': 'theQuestion2',
            'questionId': 345,
            'questionType': 'free text',
            'responses': [
                {'responseId': 144, 'selected': True, 'value': 'theResponse3'},
            ],
            'skipped': True,
        }
    ]
    result = tested.load_from_llm(123, "theQuestionnaire", data)
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
        ]
    )
    assert result == expected
