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


@patch("hyperscribe.scribe.recommendations.questionnaire_fill.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_questionnaire_details_success_scored(mock_model: MagicMock, mock_cmd_class: MagicMock) -> None:
    questionnaire = MagicMock()
    questionnaire.dbid = 42
    questionnaire.id = "ext-uuid"
    questionnaire.name = "PHQ-9"
    questionnaire.scoring_function_name = "phq9_score"
    mock_model.objects.get.return_value = questionnaire

    option_a = MagicMock()
    option_a.dbid = 10
    option_a.name = "Not at all"
    option_a.code = "LA6568-5"
    option_a.value = "0"
    option_b = MagicMock()
    option_b.dbid = 11
    option_b.name = "Several days"
    option_b.code = "LA6569-3"
    option_b.value = "1"

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
                "is_scored": True,
                "scoring_function_name": "phq9_score",
                "questions": [
                    {
                        "dbid": 1,
                        "label": "Little interest or pleasure in doing things?",
                        "type": ResponseOption.TYPE_RADIO,
                        "options": [
                            {"dbid": 10, "value": "Not at all", "code": "LA6568-5", "score_value": "0"},
                            {"dbid": 11, "value": "Several days", "code": "LA6569-3", "score_value": "1"},
                        ],
                    }
                ],
            },
            status_code=HTTPStatus.OK,
        )
    ]


@patch("hyperscribe.scribe.recommendations.questionnaire_fill.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_questionnaire_details_preserves_integer_zero_score_value(
    mock_model: MagicMock, mock_cmd_class: MagicMock
) -> None:
    """Integer 0 is a clinically meaningful score on PHQ-9-style instruments ("Not at all" = 0).
    The serializer must preserve it as the string "0", not collapse it to "" via a falsy coerce."""
    questionnaire = MagicMock()
    questionnaire.dbid = 42
    questionnaire.id = "ext-uuid"
    questionnaire.name = "PHQ-9"
    questionnaire.scoring_function_name = "phq9_score"
    mock_model.objects.get.return_value = questionnaire

    option_zero = MagicMock()
    option_zero.dbid = 10
    option_zero.name = "Not at all"
    option_zero.code = "LA6568-5"
    option_zero.value = 0  # int 0, not "0" — would be silently dropped by `or ""`

    option_none = MagicMock()
    option_none.dbid = 11
    option_none.name = "Unknown"
    option_none.code = None
    option_none.value = None

    question = MagicMock()
    question.id = "1"
    question.label = "Little interest or pleasure in doing things?"
    question.type = ResponseOption.TYPE_RADIO
    question.options = [option_zero, option_none]

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
                "is_scored": True,
                "scoring_function_name": "phq9_score",
                "questions": [
                    {
                        "dbid": 1,
                        "label": "Little interest or pleasure in doing things?",
                        "type": ResponseOption.TYPE_RADIO,
                        "options": [
                            {"dbid": 10, "value": "Not at all", "code": "LA6568-5", "score_value": "0"},
                            {"dbid": 11, "value": "Unknown", "code": "", "score_value": ""},
                        ],
                    }
                ],
            },
            status_code=HTTPStatus.OK,
        )
    ]


@patch("hyperscribe.scribe.recommendations.questionnaire_fill.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_questionnaire_details_success_unscored(mock_model: MagicMock, mock_cmd_class: MagicMock) -> None:
    questionnaire = MagicMock()
    questionnaire.dbid = 7
    questionnaire.id = "ext-uuid"
    questionnaire.name = "Intake"
    questionnaire.scoring_function_name = ""
    mock_model.objects.get.return_value = questionnaire

    option = MagicMock()
    option.dbid = 20
    option.name = "Yes"
    option.code = ""
    option.value = ""

    question = MagicMock()
    question.id = "1"
    question.label = "Do you smoke?"
    question.type = ResponseOption.TYPE_RADIO
    question.options = [option]

    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    view = _helper_instance()
    view.request.query_params = {"dbid": "7"}
    result = view.get_questionnaire_details()
    assert result == [
        JSONResponse(
            {
                "questionnaire_dbid": 7,
                "questionnaire_name": "Intake",
                "is_scored": False,
                "scoring_function_name": "",
                "questions": [
                    {
                        "dbid": 1,
                        "label": "Do you smoke?",
                        "type": ResponseOption.TYPE_RADIO,
                        "options": [
                            {"dbid": 20, "value": "Yes", "code": "", "score_value": ""},
                        ],
                    }
                ],
            },
            status_code=HTTPStatus.OK,
        )
    ]


# --- /fill-questionnaires ---


def _fill_view(secrets: dict[str, str] | None = None, body: bytes = b"{}") -> ScribeSessionView:
    view = _helper_instance()
    view.secrets = {"AnthropicAPIKey": "key", **(secrets or {})}
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-key"},
        query_params={},
        body=body,
    )
    return view


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_rejects_invalid_json(mock_auth: MagicMock) -> None:
    response = _fill_view(body=b"{not json").post_fill_questionnaires()[0]
    assert isinstance(response, JSONResponse)
    assert response.status_code == HTTPStatus.BAD_REQUEST


@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_requires_dbids(mock_auth: MagicMock) -> None:
    response = _fill_view(body=b'{"note_uuid": "n1"}').post_fill_questionnaires()[0]
    assert response.status_code == HTTPStatus.BAD_REQUEST


@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="other-staff")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_respects_the_staffer_gate(mock_auth: MagicMock, mock_provider: MagicMock) -> None:
    view = _fill_view(
        secrets={"ScribeQuestionnaireFillStaffers": "allowed1, allowed2"},
        body=b'{"note_uuid": "n1", "questionnaire_dbids": [7]}',
    )
    response = view.post_fill_questionnaires()[0]
    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.content) == {"results": [], "disabled": True}


@patch("hyperscribe.scribe.api.session_view._load_transcript", return_value={"items": [], "finalized": False})
@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="staff-key")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_refuses_an_unfinalized_transcript(
    mock_auth: MagicMock, mock_provider: MagicMock, mock_transcript: MagicMock
) -> None:
    """Drafting from a partial transcript answers questions the visit has not reached, and
    the grounding rule cannot catch it because the quote it cites is genuinely real."""
    view = _fill_view(body=b'{"note_uuid": "n1", "questionnaire_dbids": [7]}')
    response = view.post_fill_questionnaires()[0]
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert "in progress" in json.loads(response.content)["error"]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.fill_questionnaires")
@patch("hyperscribe.scribe.api.session_view._parse_transcript")
@patch("hyperscribe.scribe.api.session_view._load_transcript", return_value={"items": [{}], "finalized": True})
@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="staff-key")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_returns_results_and_audits_success(
    mock_auth: MagicMock,
    mock_provider: MagicMock,
    mock_load: MagicMock,
    mock_parse: MagicMock,
    mock_fill: MagicMock,
    mock_audit: MagicMock,
) -> None:
    outcome = SimpleNamespace(
        questionnaire_dbid=7,
        data={"questionnaire_dbid": 7, "questions": []},
        drafted=3,
        error=None,
        items=[],
    )
    mock_fill.return_value = ([outcome], {"chunks": 2, "cache_read_tokens": 900, "cache_write_tokens": 0})

    view = _fill_view(body=b'{"note_uuid": "n1", "questionnaire_dbids": [7]}')
    response = view.post_fill_questionnaires()[0]

    assert response.status_code == HTTPStatus.OK
    payload = json.loads(response.content)
    assert payload["results"][0]["drafted"] == 3
    assert payload["results"][0]["error"] is None
    event_types = [call.args[1] for call in mock_audit.call_args_list]
    assert event_types == ["QUESTIONNAIRE_FILLED"]
    # Telemetry rides on the audit row so a run with no cache reads is diagnosable later.
    assert mock_audit.call_args_list[0].args[2]["cache_read_tokens"] == 900


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.fill_questionnaires")
@patch("hyperscribe.scribe.api.session_view._parse_transcript")
@patch("hyperscribe.scribe.api.session_view._load_transcript", return_value={"items": [{}], "finalized": True})
@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="staff-key")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_audits_a_failure(
    mock_auth: MagicMock,
    mock_provider: MagicMock,
    mock_load: MagicMock,
    mock_parse: MagicMock,
    mock_fill: MagicMock,
    mock_audit: MagicMock,
) -> None:
    """A silent failure is the exact defect this replaces, so the audit row is the point."""
    outcome = SimpleNamespace(questionnaire_dbid=7, data=None, drafted=0, error="LLM returned 500", items=[])
    mock_fill.return_value = ([outcome], {"chunks": 1})

    view = _fill_view(body=b'{"note_uuid": "n1", "questionnaire_dbids": [7]}')
    response = view.post_fill_questionnaires()[0]

    assert response.status_code == HTTPStatus.OK
    assert json.loads(response.content)["results"][0]["error"] == "LLM returned 500"
    assert [call.args[1] for call in mock_audit.call_args_list] == ["QUESTIONNAIRE_FILL_FAILED"]


@patch("hyperscribe.scribe.api.session_view.audit_event")
@patch("hyperscribe.scribe.api.session_view.fill_questionnaires", side_effect=RuntimeError("boom"))
@patch("hyperscribe.scribe.api.session_view._parse_transcript")
@patch("hyperscribe.scribe.api.session_view._load_transcript", return_value={"items": [{}], "finalized": True})
@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="staff-key")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_unhandled_error_is_audited_not_swallowed(
    mock_auth: MagicMock,
    mock_provider: MagicMock,
    mock_load: MagicMock,
    mock_parse: MagicMock,
    mock_fill: MagicMock,
    mock_audit: MagicMock,
) -> None:
    view = _fill_view(body=b'{"note_uuid": "n1", "questionnaire_dbids": [7]}')
    response = view.post_fill_questionnaires()[0]
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert [call.args[1] for call in mock_audit.call_args_list] == ["QUESTIONNAIRE_FILL_FAILED"]


@patch("hyperscribe.scribe.api.session_view.fill_questionnaires")
@patch("hyperscribe.scribe.api.session_view._parse_transcript")
@patch("hyperscribe.scribe.api.session_view._load_transcript", return_value={"items": [{}], "finalized": True})
@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="staff-key")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_model_and_effort_come_from_secrets(
    mock_auth: MagicMock,
    mock_provider: MagicMock,
    mock_load: MagicMock,
    mock_parse: MagicMock,
    mock_fill: MagicMock,
) -> None:
    mock_fill.return_value = ([], {"chunks": 0})
    view = _fill_view(
        secrets={"ScribeFillModel": "claude-sonnet-5", "ScribeFillEffort": "low"},
        body=b'{"note_uuid": "n1", "questionnaire_dbids": [7]}',
    )
    view.post_fill_questionnaires()
    assert mock_fill.call_args.kwargs["model"] == "claude-sonnet-5"
    assert mock_fill.call_args.kwargs["effort"] == "low"


@patch("hyperscribe.scribe.api.session_view.fill_questionnaires")
@patch("hyperscribe.scribe.api.session_view._parse_transcript")
@patch("hyperscribe.scribe.api.session_view._load_transcript", return_value={"items": [{}], "finalized": True})
@patch("hyperscribe.scribe.api.session_view._note_provider_id", return_value="staff-key")
@patch("hyperscribe.scribe.api.session_view._authorize_edit", return_value=None)
def test_fill_questionnaires_accepts_a_single_dbid(
    mock_auth: MagicMock,
    mock_provider: MagicMock,
    mock_load: MagicMock,
    mock_parse: MagicMock,
    mock_fill: MagicMock,
) -> None:
    """The card's own button sends one questionnaire; the automatic path sends the batch."""
    mock_fill.return_value = ([], {"chunks": 0})
    view = _fill_view(body=b'{"note_uuid": "n1", "questionnaire_dbid": 7}')
    view.post_fill_questionnaires()
    assert mock_fill.call_args.args[0] == [7]
