from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.response import Response
from tests.helper import is_namedtuple


def test_class():
    tested = Question
    fields = {
        "dbid": int,
        "label": str,
        "type": QuestionType,
        "skipped": bool | None,
        "responses": list[Response],
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tested = Question(
        dbid=123,
        label="theQuestion",
        type=QuestionType.TYPE_RADIO,
        skipped=False,
        responses=[
            Response(dbid=234, value="456", selected=False, comment="theComment"),
            Response(dbid=456, value=789, selected=True, comment="aComment"),
        ]
    )
    result = tested.to_json()
    expected = {
        'dbid': 123,
        'label': 'theQuestion',
        'responses': [
            {'dbid': 234, 'selected': False, 'value': '456', 'comment': 'theComment'},
            {'dbid': 456, 'selected': True, 'value': 789, 'comment': 'aComment'},
        ],
        'skipped': False,
        'type': 'SING',
    }
    assert result == expected


def test_for_llm():
    tests = [
        (
            QuestionType.TYPE_RADIO,
            True,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456'},
                    {'responseId': 456, 'selected': True, 'value': 789},
                ],
                'skipped': False,
                'questionType': 'single choice',
            }
        ),
        (
            QuestionType.TYPE_RADIO,
            False,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456'},
                    {'responseId': 456, 'selected': True, 'value': 789},
                ],
                'questionType': 'single choice',
            }
        ),
        (
            QuestionType.TYPE_CHECKBOX,
            False,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {
                        'responseId': 234,
                        'selected': False,
                        'value': '456',
                        'comment': 'theComment',
                        "description": "add in the comment key any relevant information expanding the answer",
                    },
                    {
                        'responseId': 456,
                        'selected': True,
                        'value': 789,
                        'comment': 'aComment',
                        "description": "add in the comment key any relevant information expanding the answer",
                    },
                ],
                'questionType': 'multiple choice',
            }
        ),
        (
            QuestionType.TYPE_TEXT,
            False,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': True, 'value': '456'},
                ],
                'questionType': 'free text',
            }
        ),
        (
            QuestionType.TYPE_INTEGER,
            True,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': True, 'value': '456'},
                ],
                'skipped': False,
                'questionType': 'integer',
            }
        ),
    ]
    for idx, (question_type, include_skipped, expected) in enumerate(tests):
        tested = Question(
            dbid=123,
            label="theQuestion",
            type=question_type,
            skipped=False,
            responses=[
                Response(dbid=234, value="456", selected=False, comment="theComment"),
                Response(dbid=456, value=789, selected=True, comment="aComment"),
            ]
        )
        result = tested.for_llm(include_skipped)
        assert result == expected, f"---> {idx}"


def test_load_from():
    tested = Question
    result = tested.load_from({
        'dbid': 123,
        'label': 'theQuestion',
        'responses': [
            {'dbid': 234, 'selected': False, 'value': '456', 'comment': 'theComment'},
            {'dbid': 456, 'selected': True, 'value': 789, 'comment': 'aComment'},
        ],
        'skipped': False,
        'type': 'SING',
    })
    expected = Question(
        dbid=123,
        label="theQuestion",
        type=QuestionType.TYPE_RADIO,
        skipped=False,
        responses=[
            Response(dbid=234, value="456", selected=False, comment="theComment"),
            Response(dbid=456, value=789, selected=True, comment="aComment"),
        ]
    )
    assert result == expected


def test_load_from_llm():
    responses_with_comment = [
        Response(dbid=234, value="456", selected=False, comment="theComment"),
        Response(dbid=456, value=789, selected=True, comment="aComment"),
    ]
    responses_no_comment = [
        Response(dbid=234, value="456", selected=False, comment=None),
        Response(dbid=456, value=789, selected=True, comment=None),
    ]

    tests = [
        (
            QuestionType.TYPE_RADIO,
            True,
            responses_no_comment,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456'},
                    {'responseId': 456, 'selected': True, 'value': 789},
                ],
                'skipped': True,
                'questionType': 'single choice',
            }
        ),
        (
            QuestionType.TYPE_RADIO,
            None,
            responses_no_comment,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456'},
                    {'responseId': 456, 'selected': True, 'value': 789},
                ],
                'questionType': 'single choice',
            }
        ),
        (
            QuestionType.TYPE_CHECKBOX,
            None,
            responses_with_comment,
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456', 'comment': 'theComment'},
                    {'responseId': 456, 'selected': True, 'value': 789, 'comment': 'aComment'},
                ],
                'questionType': 'multiple choice',
            }
        ),
        (
            QuestionType.TYPE_TEXT,
            None,
            responses_no_comment[:1],
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456'},
                ],
                'questionType': 'free text',
            }
        ),
        (
            QuestionType.TYPE_INTEGER,
            False,
            responses_no_comment[:1],
            {
                'questionId': 123,
                'question': 'theQuestion',
                'responses': [
                    {'responseId': 234, 'selected': False, 'value': '456'},
                ],
                'skipped': False,
                'questionType': 'integer',
            }
        ),
    ]
    for idx, (exp_question_type, exp_include_skipped, exp_responses, data) in enumerate(tests):
        tested = Question

        expected = Question(
            dbid=123,
            label="theQuestion",
            type=exp_question_type,
            skipped=exp_include_skipped,
            responses=exp_responses,
        )
        result = tested.load_from_llm(data)
        assert result == expected, f"---> {idx}"
