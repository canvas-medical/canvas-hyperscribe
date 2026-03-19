import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.commands.commands.questionnaire.question import ResponseOption
from canvas_sdk.effects.simple_api import JSONResponse

from hyperscribe.scribe.api.session_view import ScribeSessionView

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


def _helper_instance(template_secret: str = "{}") -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    secrets: dict[str, str] = {
        "ScribeBackend": '{"vendor": "nabla", "client_id": "id", "client_secret": "secret"}',
        "VisitTemplates": template_secret,
    }
    environment: dict[str, str] = {}
    view = ScribeSessionView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-key"},
        query_params={},
        body=b"",
    )
    return view


def test_get_visit_templates_no_secret() -> None:
    view = _helper_instance(template_secret="{}")
    result = view.get_visit_templates()
    assert result == [JSONResponse({"templates": []}, status_code=HTTPStatus.OK)]


def test_get_visit_templates_invalid_json() -> None:
    view = _helper_instance(template_secret="not valid json {{{")
    result = view.get_visit_templates()
    assert result == [JSONResponse({"templates": []}, status_code=HTTPStatus.OK)]


def test_get_visit_templates_empty_templates() -> None:
    view = _helper_instance(template_secret=json.dumps({"templates": []}))
    result = view.get_visit_templates()
    assert result == [JSONResponse({"templates": []}, status_code=HTTPStatus.OK)]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_get_visit_templates_resolves_questionnaires(mock_model: MagicMock, mock_cmd_class: MagicMock) -> None:
    q1 = MagicMock()
    q1.dbid = 10
    q1.id = "ext-uuid-1"
    q1.name = "PHQ-9"

    q2 = MagicMock()
    q2.dbid = 20
    q2.id = "ext-uuid-2"
    q2.name = "GAD-7"

    # Batch filter returns both questionnaires as an iterable.
    mock_model.objects.filter.return_value = [q1, q2]

    option_a = MagicMock()
    option_a.dbid = 101
    option_a.name = "Not at all"
    option_b = MagicMock()
    option_b.dbid = 102
    option_b.name = "Several days"

    question = MagicMock()
    question.id = "1"
    question.label = "Little interest?"
    question.type = ResponseOption.TYPE_RADIO
    question.options = [option_a, option_b]

    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    secret = json.dumps(
        {
            "templates": [
                {"name": "Initial Visit", "questionnaires": ["PHQ-9", "GAD-7"]},
                {"name": "Follow-Up", "questionnaires": []},
            ]
        }
    )
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()

    expected_question = {
        "dbid": 1,
        "label": "Little interest?",
        "type": ResponseOption.TYPE_RADIO,
        "options": [
            {"dbid": 101, "value": "Not at all"},
            {"dbid": 102, "value": "Several days"},
        ],
    }
    assert result == [
        JSONResponse(
            {
                "templates": [
                    {
                        "name": "Initial Visit",
                        "questionnaires": [
                            {
                                "questionnaire_dbid": 10,
                                "questionnaire_name": "PHQ-9",
                                "questions": [expected_question],
                            },
                            {
                                "questionnaire_dbid": 20,
                                "questionnaire_name": "GAD-7",
                                "questions": [expected_question],
                            },
                        ],
                    },
                    {"name": "Follow-Up", "questionnaires": []},
                ]
            },
            status_code=HTTPStatus.OK,
        )
    ]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_get_visit_templates_skips_missing_questionnaire(mock_model: MagicMock, mock_cmd_class: MagicMock) -> None:
    q1 = MagicMock()
    q1.dbid = 10
    q1.id = "ext-uuid-1"
    q1.name = "PHQ-9"

    # Batch filter only returns PHQ-9 (NonExistent is missing).
    mock_model.objects.filter.return_value = [q1]

    cmd_instance = MagicMock()
    cmd_instance.questions = []
    mock_cmd_class.return_value = cmd_instance

    secret = json.dumps({"templates": [{"name": "Test", "questionnaires": ["PHQ-9", "NonExistent"]}]})
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()

    assert result == [
        JSONResponse(
            {
                "templates": [
                    {
                        "name": "Test",
                        "questionnaires": [
                            {
                                "questionnaire_dbid": 10,
                                "questionnaire_name": "PHQ-9",
                                "questions": [],
                            }
                        ],
                    }
                ]
            },
            status_code=HTTPStatus.OK,
        )
    ]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_get_visit_templates_no_questionnaire_names(mock_model: MagicMock, mock_cmd_class: MagicMock) -> None:
    """Templates with no questionnaires should not trigger any DB queries."""
    secret = json.dumps({"templates": [{"name": "Sick Visit", "questionnaires": []}]})
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()

    mock_model.objects.filter.assert_not_called()
    assert result == [
        JSONResponse(
            {"templates": [{"name": "Sick Visit", "questionnaires": []}]},
            status_code=HTTPStatus.OK,
        )
    ]
