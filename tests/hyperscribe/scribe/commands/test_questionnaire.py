from unittest.mock import MagicMock, patch

from canvas_sdk.commands.commands.questionnaire.question import (
    CheckboxQuestion,
    IntegerQuestion,
    RadioQuestion,
    ResponseOption,
    TextQuestion,
)

from hyperscribe.scribe.commands.questionnaire import QuestionnaireParser


def test_extract_returns_none() -> None:
    parser = QuestionnaireParser()
    assert parser.extract("any text") is None


def test_extract_all_returns_empty() -> None:
    parser = QuestionnaireParser()
    assert parser.extract_all("any text") == []


def _make_question(q_id: str, q_type: str, options: list[tuple[int, str, str, str]]) -> MagicMock:
    """Build a mock SDK question with real ResponseOption objects."""
    question = MagicMock()
    question.id = q_id
    question.name = f"question-{q_id}"
    question.label = f"Question {q_id}"
    question.type = q_type
    question.coding = {"system": "SNOMED", "code": "12345"}
    question.options = [
        ResponseOption(dbid=dbid, name=name, code=code, value=value) for dbid, name, code, value in options
    ]
    return question


@patch("hyperscribe.scribe.commands.questionnaire.Questionnaire")
@patch("hyperscribe.scribe.commands.questionnaire.QuestionnaireCommand")
def test_build_radio(mock_cmd_class: MagicMock, mock_qs_model: MagicMock) -> None:
    parser = QuestionnaireParser()
    questionnaire = MagicMock()
    questionnaire.id = "ext-uuid"
    mock_qs_model.objects.get.return_value = questionnaire

    question = _make_question(
        "1",
        ResponseOption.TYPE_RADIO,
        [(10, "Not at all", "LA1", ""), (11, "Several days", "LA2", "")],
    )
    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    data = {
        "questionnaire_dbid": 42,
        "questions": [
            {
                "dbid": 1,
                "responses": [
                    {"dbid": 10, "value": "Not at all", "selected": False},
                    {"dbid": 11, "value": "Several days", "selected": True},
                ],
            },
        ],
    }
    result = parser.build(data, "note-uuid", "cmd-uuid")

    # Questions are replaced with hand-built objects.
    assert len(cmd_instance.questions) == 1
    built_q = cmd_instance.questions[0]
    assert isinstance(built_q, RadioQuestion)
    assert built_q.response == 11  # dbid of selected option


@patch("hyperscribe.scribe.commands.questionnaire.Questionnaire")
@patch("hyperscribe.scribe.commands.questionnaire.QuestionnaireCommand")
def test_build_checkbox(mock_cmd_class: MagicMock, mock_qs_model: MagicMock) -> None:
    parser = QuestionnaireParser()
    questionnaire = MagicMock()
    questionnaire.id = "ext-uuid"
    mock_qs_model.objects.get.return_value = questionnaire

    question = _make_question(
        "1",
        ResponseOption.TYPE_CHECKBOX,
        [(10, "Option A", "C1", ""), (11, "Option B", "C2", "")],
    )
    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    data = {
        "questionnaire_dbid": 42,
        "questions": [
            {
                "dbid": 1,
                "responses": [
                    {"dbid": 10, "value": "Option A", "selected": True, "comment": "note"},
                    {"dbid": 11, "value": "Option B", "selected": False, "comment": ""},
                ],
            },
        ],
    }
    parser.build(data, "note-uuid", "cmd-uuid")

    built_q = cmd_instance.questions[0]
    assert isinstance(built_q, CheckboxQuestion)
    assert built_q.response == [
        {"text": "Option A", "value": 10, "comment": "note", "selected": True},
        {"text": "Option B", "value": 11, "comment": "", "selected": False},
    ]


@patch("hyperscribe.scribe.commands.questionnaire.Questionnaire")
@patch("hyperscribe.scribe.commands.questionnaire.QuestionnaireCommand")
def test_build_text(mock_cmd_class: MagicMock, mock_qs_model: MagicMock) -> None:
    parser = QuestionnaireParser()
    questionnaire = MagicMock()
    questionnaire.id = "ext-uuid"
    mock_qs_model.objects.get.return_value = questionnaire

    question = _make_question("1", ResponseOption.TYPE_TEXT, [(10, "answer", "T1", "")])
    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    data = {
        "questionnaire_dbid": 42,
        "questions": [
            {
                "dbid": 1,
                "responses": [{"dbid": 10, "value": "Patient reports fatigue", "selected": False}],
            },
        ],
    }
    parser.build(data, "note-uuid", "cmd-uuid")

    built_q = cmd_instance.questions[0]
    assert isinstance(built_q, TextQuestion)
    assert built_q.response == "Patient reports fatigue"


@patch("hyperscribe.scribe.commands.questionnaire.Questionnaire")
@patch("hyperscribe.scribe.commands.questionnaire.QuestionnaireCommand")
def test_build_integer(mock_cmd_class: MagicMock, mock_qs_model: MagicMock) -> None:
    parser = QuestionnaireParser()
    questionnaire = MagicMock()
    questionnaire.id = "ext-uuid"
    mock_qs_model.objects.get.return_value = questionnaire

    question = _make_question("1", ResponseOption.TYPE_INTEGER, [(10, "score", "I1", "")])
    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    data = {
        "questionnaire_dbid": 42,
        "questions": [
            {
                "dbid": 1,
                "responses": [{"dbid": 10, "value": "7", "selected": False}],
            },
        ],
    }
    parser.build(data, "note-uuid", "cmd-uuid")

    built_q = cmd_instance.questions[0]
    assert isinstance(built_q, IntegerQuestion)
    assert built_q.response == 7


@patch("hyperscribe.scribe.commands.questionnaire.Questionnaire")
@patch("hyperscribe.scribe.commands.questionnaire.QuestionnaireCommand")
def test_build_skips_unmatched_questions(mock_cmd_class: MagicMock, mock_qs_model: MagicMock) -> None:
    """Questions with no matching frontend data are kept as-is (no response)."""
    parser = QuestionnaireParser()
    questionnaire = MagicMock()
    questionnaire.id = "ext-uuid"
    mock_qs_model.objects.get.return_value = questionnaire

    question = _make_question("999", ResponseOption.TYPE_TEXT, [])
    cmd_instance = MagicMock()
    cmd_instance.questions = [question]
    mock_cmd_class.return_value = cmd_instance

    data = {"questionnaire_dbid": 42, "questions": []}
    parser.build(data, "note-uuid", "cmd-uuid")

    # Unmatched question is kept as the original mock, not replaced.
    assert cmd_instance.questions[0] is question
