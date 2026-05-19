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
    q1.scoring_function_name = "phq9_score"

    q2 = MagicMock()
    q2.dbid = 20
    q2.id = "ext-uuid-2"
    q2.name = "GAD-7"
    q2.scoring_function_name = "gad7_score"

    # Batch filter returns both questionnaires as an iterable.
    mock_model.objects.filter.return_value = [q1, q2]

    option_a = MagicMock()
    option_a.dbid = 101
    option_a.name = "Not at all"
    option_a.code = "LA6568-5"
    option_a.value = "0"
    option_b = MagicMock()
    option_b.dbid = 102
    option_b.name = "Several days"
    option_b.code = "LA6569-3"
    option_b.value = "1"

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
            {"dbid": 101, "value": "Not at all", "code": "LA6568-5", "score_value": "0"},
            {"dbid": 102, "value": "Several days", "code": "LA6569-3", "score_value": "1"},
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
                                "is_scored": True,
                                "scoring_function_name": "phq9_score",
                                "questions": [expected_question],
                            },
                            {
                                "questionnaire_dbid": 20,
                                "questionnaire_name": "GAD-7",
                                "is_scored": True,
                                "scoring_function_name": "gad7_score",
                                "questions": [expected_question],
                            },
                        ],
                        "ros_sections": None,
                        "pe_sections": None,
                        "charges": [],
                    },
                    {
                        "name": "Follow-Up",
                        "questionnaires": [],
                        "ros_sections": None,
                        "pe_sections": None,
                        "charges": [],
                    },
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
    q1.scoring_function_name = "phq9_score"

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
                                "is_scored": True,
                                "scoring_function_name": "phq9_score",
                                "questions": [],
                            }
                        ],
                        "ros_sections": None,
                        "pe_sections": None,
                        "charges": [],
                    }
                ]
            },
            status_code=HTTPStatus.OK,
        )
    ]


@patch("hyperscribe.scribe.api.session_view.QuestionnaireCommand")
@patch("hyperscribe.scribe.api.session_view.QuestionnaireModel")
def test_get_visit_templates_preserves_integer_zero_score_value(
    mock_model: MagicMock, mock_cmd_class: MagicMock
) -> None:
    """Template-resolved questionnaires must preserve int 0 score_values as the string "0".
    Mirror of the /questionnaire-details test for the visit-template resolution path."""
    q1 = MagicMock()
    q1.dbid = 10
    q1.id = "ext-uuid-1"
    q1.name = "PHQ-9"
    q1.scoring_function_name = "phq9_score"
    mock_model.objects.filter.return_value = [q1]

    option_zero = MagicMock()
    option_zero.dbid = 101
    option_zero.name = "Not at all"
    option_zero.code = "LA6568-5"
    option_zero.value = 0  # int 0; must serialize as "0"

    option_none = MagicMock()
    option_none.dbid = 102
    option_none.name = "Unknown"
    option_none.code = None
    option_none.value = None

    question = MagicMock()
    question.id = "1"
    question.label = "Little interest?"
    question.type = ResponseOption.TYPE_RADIO
    question.options = [option_zero, option_none]

    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    secret = json.dumps({"templates": [{"name": "Test", "questionnaires": ["PHQ-9"]}]})
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
                                "is_scored": True,
                                "scoring_function_name": "phq9_score",
                                "questions": [
                                    {
                                        "dbid": 1,
                                        "label": "Little interest?",
                                        "type": ResponseOption.TYPE_RADIO,
                                        "options": [
                                            {"dbid": 101, "value": "Not at all", "code": "LA6568-5", "score_value": "0"},
                                            {"dbid": 102, "value": "Unknown", "code": "", "score_value": ""},
                                        ],
                                    }
                                ],
                            }
                        ],
                        "ros_sections": None,
                        "pe_sections": None,
                        "charges": [],
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
            {
                "templates": [
                    {
                        "name": "Sick Visit",
                        "questionnaires": [],
                        "ros_sections": None,
                        "pe_sections": None,
                        "charges": [],
                    }
                ]
            },
            status_code=HTTPStatus.OK,
        )
    ]


def test_get_visit_templates_parses_ros_and_pe() -> None:
    secret = json.dumps(
        {
            "templates": [
                {
                    "name": "Initial Visit",
                    "questionnaires": [],
                    "ros_template": "CONSTITUTIONAL: Denies fever.\nEYES: Denies visual changes.",
                    "pe_template": "GENERAL: NAD. Well-developed.\nHEENT: NCAT.",
                }
            ]
        }
    )
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()
    assert result == [
        JSONResponse(
            {
                "templates": [
                    {
                        "name": "Initial Visit",
                        "questionnaires": [],
                        "ros_sections": [
                            {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever."},
                            {"key": "eyes", "title": "EYES", "text": "Denies visual changes."},
                        ],
                        "pe_sections": [
                            {"key": "general", "title": "GENERAL", "text": "NAD. Well-developed."},
                            {"key": "heent", "title": "HEENT", "text": "NCAT."},
                        ],
                        "charges": [],
                    }
                ]
            },
            status_code=HTTPStatus.OK,
        )
    ]


def test_get_visit_templates_null_ros_pe() -> None:
    secret = json.dumps(
        {
            "templates": [
                {
                    "name": "Follow-Up",
                    "questionnaires": [],
                    "ros_template": None,
                    "pe_template": None,
                }
            ]
        }
    )
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()
    assert result == [
        JSONResponse(
            {
                "templates": [
                    {
                        "name": "Follow-Up",
                        "questionnaires": [],
                        "ros_sections": None,
                        "pe_sections": None,
                        "charges": [],
                    }
                ]
            },
            status_code=HTTPStatus.OK,
        )
    ]


@patch("hyperscribe.scribe.api.session_view.ChargeDescriptionMaster")
def test_get_visit_templates_resolves_charges(mock_cdm: MagicMock) -> None:
    record_99342 = MagicMock()
    record_99342.cpt_code = "99342"
    record_99342.short_name = "Home visit new"
    record_99342.name = "Home visit new patient"

    record_g2211 = MagicMock()
    record_g2211.cpt_code = "G2211"
    record_g2211.short_name = "Visit complexity"
    record_g2211.name = "Visit complexity add-on"

    mock_cdm.objects.filter.return_value = [record_99342, record_g2211]

    secret = json.dumps(
        {
            "templates": [
                {
                    "name": "Home Visit",
                    "questionnaires": [],
                    "charges": ["99342", "G2211"],
                }
            ]
        }
    )
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()

    data = json.loads(result[0].content)
    charges = data["templates"][0]["charges"]
    assert len(charges) == 2
    assert charges[0] == {"cpt_code": "99342", "description": "Home visit new"}
    assert charges[1] == {"cpt_code": "G2211", "description": "Visit complexity"}


@patch("hyperscribe.scribe.api.session_view.ChargeDescriptionMaster")
def test_get_visit_templates_drops_invalid_charges(mock_cdm: MagicMock) -> None:
    record = MagicMock()
    record.cpt_code = "99342"
    record.short_name = "Home visit new"
    record.name = "Home visit new patient"

    # Only 99342 exists; XXXXX does not.
    mock_cdm.objects.filter.return_value = [record]

    secret = json.dumps(
        {
            "templates": [
                {
                    "name": "Test",
                    "questionnaires": [],
                    "charges": ["99342", "XXXXX"],
                }
            ]
        }
    )
    view = _helper_instance(template_secret=secret)
    result = view.get_visit_templates()

    data = json.loads(result[0].content)
    charges = data["templates"][0]["charges"]
    assert len(charges) == 1
    assert charges[0]["cpt_code"] == "99342"
