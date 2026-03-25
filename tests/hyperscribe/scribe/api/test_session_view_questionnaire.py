import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.commands.commands.questionnaire.question import ResponseOption
from canvas_sdk.effects.simple_api import JSONResponse

from hyperscribe.scribe.api.session_view import ScribeSessionView

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


def _helper_instance() -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    secrets: dict[str, str] = {"ScribeBackend": '{"vendor": "nabla", "client_id": "id", "client_secret": "secret"}'}
    environment: dict[str, str] = {}
    view = ScribeSessionView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-key"},
        query_params={},
        body=b"",
    )
    return view


# --- /search-questionnaires ---


@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_search_questionnaires_empty_query_returns_all(mock_model: MagicMock) -> None:
    q1 = MagicMock()
    q1.dbid = 1
    q1.name = "PHQ-9"

    qs = MagicMock()
    qs.order_by.return_value = qs
    qs.__getitem__ = MagicMock(return_value=[q1])
    mock_model.objects.filter.return_value = qs

    view = _helper_instance()
    view.request.query_params = {"query": ""}
    result = view.get_search_questionnaires()
    mock_model.objects.filter.assert_called_once_with(status="AC", use_case_in_charting="QUES")
    # No additional .filter() for query text
    qs.filter.assert_not_called()
    assert result == [JSONResponse({"results": [{"dbid": 1, "name": "PHQ-9"}]}, status_code=HTTPStatus.OK)]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_search_questionnaires_with_query(mock_model: MagicMock) -> None:
    q1 = MagicMock()
    q1.dbid = 1
    q1.name = "PHQ-9"
    q2 = MagicMock()
    q2.dbid = 2
    q2.name = "PHQ-2"

    qs = MagicMock()
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.__getitem__ = MagicMock(return_value=[q1, q2])
    mock_model.objects.filter.return_value = qs

    view = _helper_instance()
    view.request.query_params = {"query": "PHQ"}
    result = view.get_search_questionnaires()
    assert result == [
        JSONResponse(
            {"results": [{"dbid": 1, "name": "PHQ-9"}, {"dbid": 2, "name": "PHQ-2"}]},
            status_code=HTTPStatus.OK,
        )
    ]


# --- /questionnaire-details ---


@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_questionnaire_details_missing_dbid(mock_model: MagicMock) -> None:
    view = _helper_instance()
    view.request.query_params = {}
    result = view.get_questionnaire_details()
    assert result == [JSONResponse({"error": "dbid required"}, status_code=HTTPStatus.BAD_REQUEST)]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_questionnaire_details_not_found(mock_model: MagicMock) -> None:
    mock_model.DoesNotExist = Exception
    mock_model.objects.get.side_effect = Exception("not found")
    view = _helper_instance()
    view.request.query_params = {"dbid": "999"}
    result = view.get_questionnaire_details()
    assert result == [JSONResponse({"error": "not found"}, status_code=HTTPStatus.NOT_FOUND)]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_questionnaire_details_success(mock_model: MagicMock, mock_cmd_class: MagicMock) -> None:
    questionnaire = MagicMock()
    questionnaire.dbid = 42
    questionnaire.id = "ext-uuid"
    questionnaire.name = "PHQ-9"
    mock_model.objects.get.return_value = questionnaire

    option_a = MagicMock()
    option_a.dbid = 10
    option_a.name = "Not at all"
    option_b = MagicMock()
    option_b.dbid = 11
    option_b.name = "Several days"

    question = MagicMock()
    question.id = "1"
    question.label = "Little interest or pleasure in doing things?"
    question.type = ResponseOption.TYPE_RADIO
    question.options = [option_a, option_b]

    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    view = _helper_instance()
    view.request.query_params = {"dbid": "42"}
    result = view.get_questionnaire_details()
    assert result == [
        JSONResponse(
            {
                "questionnaire_dbid": 42,
                "questionnaire_name": "PHQ-9",
                "questions": [
                    {
                        "dbid": 1,
                        "label": "Little interest or pleasure in doing things?",
                        "type": ResponseOption.TYPE_RADIO,
                        "options": [
                            {"dbid": 10, "value": "Not at all"},
                            {"dbid": 11, "value": "Several days"},
                        ],
                    }
                ],
            },
            status_code=HTTPStatus.OK,
        )
    ]
