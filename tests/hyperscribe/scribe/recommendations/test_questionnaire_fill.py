from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens
from canvas_sdk.commands.commands.questionnaire.question import ResponseOption

from hyperscribe.scribe.backend.models import Transcript, TranscriptItem
from hyperscribe.scribe.recommendations.questionnaire_fill import (
    _apply_grounding_gate,
    build_fill_command_data,
    fill_questionnaire,
)
from hyperscribe.scribe.recommendations.schemas import (
    EvidenceTurn,
    QuestionnaireFillResult,
    QuestionnaireItemFill,
)

# BaseModelLlmJson uses ConfigDict(extra="forbid", alias_generator=to_camel) without populate_by_name,
# so model construction and the LLM response JSON both key on camelCase aliases (questionDbid, itemId, ...).


def _questions() -> list[dict]:
    return [
        {"dbid": 10, "label": "Profession?", "type": ResponseOption.TYPE_TEXT, "options": []},
        {"dbid": 11, "label": "How many days?", "type": ResponseOption.TYPE_INTEGER, "options": []},
        {
            "dbid": 12,
            "label": "Interest or pleasure in doing things?",
            "type": ResponseOption.TYPE_RADIO,
            "options": [{"dbid": 100, "value": "Not at all"}, {"dbid": 101, "value": "Several days"}],
        },
        {
            "dbid": 13,
            "label": "Which symptoms?",
            "type": ResponseOption.TYPE_CHECKBOX,
            "options": [{"dbid": 200, "value": "Cough"}, {"dbid": 201, "value": "Fever"}],
        },
    ]


def _transcript(item_ids: tuple[str, str] = ("t1", "t2")) -> Transcript:
    return Transcript(
        items=[
            TranscriptItem(
                text="how are you", speaker="provider", start_offset_ms=0, end_offset_ms=1, item_id=item_ids[0]
            ),
            TranscriptItem(
                text="not great", speaker="patient", start_offset_ms=1, end_offset_ms=2, item_id=item_ids[1]
            ),
        ]
    )


def _client(response_data: dict | None, code: HTTPStatus = HTTPStatus.OK) -> MagicMock:
    client = MagicMock()
    if response_data is not None:
        client.request.return_value = LlmResponse(
            code=code, response=json.dumps(response_data), tokens=LlmTokens(prompt=10, generated=5)
        )
    return client


def _ev(item_id: str = "t1") -> dict:
    return {"speaker": "patient", "quote": "...", "itemId": item_id}


# --- build_fill_command_data (pure mapper) ---


def test_mapper_text_and_integer() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[
            QuestionnaireItemFill(questionDbid=10, status="answered", value="Nurse"),
            QuestionnaireItemFill(questionDbid=11, status="answered", value="14"),
        ],
    )
    data = build_fill_command_data(result, _questions())
    assert data == {
        "questionnaire_dbid": 1,
        "questions": [
            {"dbid": 10, "responses": [{"value": "Nurse", "selected": True, "comment": None}]},
            {"dbid": 11, "responses": [{"value": "14", "selected": True, "comment": None}]},
        ],
    }


def test_mapper_radio_selects_one_positionally() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[QuestionnaireItemFill(questionDbid=12, status="answered", selectedOptionDbid=101)],
    )
    data = build_fill_command_data(result, _questions())
    assert data["questions"] == [
        {
            "dbid": 12,
            "responses": [
                {"value": "Not at all", "selected": False, "comment": None},
                {"value": "Several days", "selected": True, "comment": None},
            ],
        }
    ]


def test_mapper_denied_radio_records_chosen_option() -> None:
    # Lossy denial: status="denied" is stored simply as selecting the option the model picked.
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[QuestionnaireItemFill(questionDbid=12, status="denied", selectedOptionDbid=100)],
    )
    data = build_fill_command_data(result, _questions())
    assert data["questions"][0]["responses"][0] == {"value": "Not at all", "selected": True, "comment": None}


def test_mapper_checkbox_affirmed_options() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[QuestionnaireItemFill(questionDbid=13, status="answered", selectedOptionDbids=[201])],
    )
    data = build_fill_command_data(result, _questions())
    assert data["questions"] == [
        {
            "dbid": 13,
            "responses": [
                {"value": "Cough", "selected": False, "comment": None},
                {"value": "Fever", "selected": True, "comment": None},
            ],
        }
    ]


def test_mapper_omits_not_assessed_and_blank() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[
            QuestionnaireItemFill(questionDbid=10, status="not_assessed"),
            QuestionnaireItemFill(questionDbid=12, status="answered", selectedOptionDbid=None),
        ],
    )
    data = build_fill_command_data(result, _questions())
    assert data == {"questionnaire_dbid": 1, "questions": []}


# --- grounding gate ---


def test_grounding_gate_drops_ungrounded() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[
            QuestionnaireItemFill(
                questionDbid=10, status="answered", value="Nurse", evidence=[EvidenceTurn(**_ev("t1"))]
            ),
            QuestionnaireItemFill(
                questionDbid=11, status="answered", value="14", evidence=[EvidenceTurn(**_ev("zzz"))]
            ),
        ],
    )
    gated = _apply_grounding_gate(result, _transcript())
    assert [i.question_dbid for i in gated.items] == [10]


def test_grounding_gate_keeps_not_assessed() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=1,
        items=[QuestionnaireItemFill(questionDbid=10, status="not_assessed")],
    )
    gated = _apply_grounding_gate(result, _transcript())
    assert [i.question_dbid for i in gated.items] == [10]


# --- fill_questionnaire (prompt + parse + gate, mock client) ---


def test_fill_questionnaire_parses_and_grounds() -> None:
    data = {
        "questionnaireDbid": 1,
        "items": [
            {"questionDbid": 10, "status": "answered", "value": "Nurse", "evidence": [_ev("t1")]},
            {"questionDbid": 11, "status": "answered", "value": "14", "evidence": [_ev("missing")]},
        ],
    }
    client = _client(data)
    result = fill_questionnaire("PHQ-9", _questions(), _transcript(), client)
    assert result is not None
    assert [i.question_dbid for i in result.items] == [10]  # ungrounded item dropped by the gate
    client.set_schema.assert_called_once_with(QuestionnaireFillResult)
    client.request.assert_called_once()


def test_fill_questionnaire_empty_transcript_returns_none() -> None:
    client = _client({"questionnaireDbid": 1, "items": []})
    assert fill_questionnaire("PHQ-9", _questions(), Transcript(items=[]), client) is None
    client.request.assert_not_called()


def test_fill_questionnaire_non_ok_returns_none() -> None:
    client = _client({"questionnaireDbid": 1, "items": []}, code=HTTPStatus.INTERNAL_SERVER_ERROR)
    assert fill_questionnaire("PHQ-9", _questions(), _transcript(), client) is None
