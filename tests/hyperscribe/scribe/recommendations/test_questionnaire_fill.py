from __future__ import annotations

import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens
from canvas_sdk.commands.commands.questionnaire.question import ResponseOption

from hyperscribe.scribe.backend.models import Transcript, TranscriptItem
from hyperscribe.scribe.recommendations.questionnaire_fill import (
    CHUNK_SIZE,
    LONG_CHUNK_SIZE,
    LONG_TRANSCRIPT_CHARS,
    SINGLE_CALL_MAX,
    FillChunkError,
    _apply_grounding_gate,
    build_fill_command_data,
    chunk_questions,
    fill_chunk,
    fill_chunk_with_retry,
    fill_questionnaires,
    failure_kind,
    resolve_questionnaire_definition,
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
            "options": [
                {"dbid": 100, "value": "Not at all", "code": "LA6568-5", "score_value": "0"},
                {"dbid": 101, "value": "Several days", "code": "LA6569-3", "score_value": "1"},
            ],
        },
        {
            "dbid": 13,
            "label": "Which symptoms?",
            "type": ResponseOption.TYPE_CHECKBOX,
            "options": [
                {"dbid": 200, "value": "Cough", "code": "", "score_value": "0"},
                {"dbid": 201, "value": "Fever", "code": "", "score_value": "2"},
            ],
        },
    ]


def _definition(questions: list[dict] | None = None, scored: bool = True) -> dict:
    return {
        "questionnaire_dbid": 7,
        "questionnaire_name": "PHQ-9",
        "is_scored": scored,
        "scoring_function_name": "sum" if scored else "",
        "questions": _questions() if questions is None else questions,
    }


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
    client.last_usage = {}
    if response_data is not None:
        client.request.return_value = LlmResponse(
            code=code, response=json.dumps(response_data), tokens=LlmTokens(prompt=10, generated=5)
        )
    return client


def _ev(item_id: str = "t1") -> dict:
    return {"speaker": "patient", "quote": "...", "itemId": item_id}


def _turn(item_id: str = "t1") -> EvidenceTurn:
    return EvidenceTurn(speaker="patient", quote="...", itemId=item_id)


def _items(*items: QuestionnaireItemFill) -> dict[int, QuestionnaireItemFill]:
    return {item.question_dbid: item for item in items}


# --- chunk_questions ---


def test_chunk_boundary_single_call_at_the_max() -> None:
    questions = [{"dbid": i} for i in range(SINGLE_CALL_MAX)]
    assert chunk_questions(questions) == [questions]


def test_chunk_boundary_splits_one_past_the_max() -> None:
    questions = [{"dbid": i} for i in range(SINGLE_CALL_MAX + 1)]
    chunks = chunk_questions(questions)
    assert len(chunks) == 2
    assert [len(c) for c in chunks] == [CHUNK_SIZE, SINGLE_CALL_MAX + 1 - CHUNK_SIZE]
    assert [q for chunk in chunks for q in chunk] == questions


def test_chunk_empty_questionnaire() -> None:
    assert chunk_questions([]) == []


# --- build_fill_command_data (pure mapper) ---


def test_mapper_emits_every_question_with_full_render_shape() -> None:
    """Unanswered questions must survive: the provider finishes the form by hand, and both
    isComplete and computeScore in questionnaire-score.js need every question and every
    score_value present."""
    data = build_fill_command_data(_definition(), _items())

    assert data["questionnaire_name"] == "PHQ-9"
    assert data["is_scored"] is True
    assert data["scoring_function_name"] == "sum"
    assert [q["dbid"] for q in data["questions"]] == [10, 11, 12, 13]

    radio = data["questions"][2]
    assert radio["label"] == "Interest or pleasure in doing things?"
    assert radio["type"] == ResponseOption.TYPE_RADIO
    assert radio["responses"] == [
        {
            "dbid": 100,
            "value": "Not at all",
            "code": "LA6568-5",
            "score_value": "0",
            "selected": False,
            "comment": None,
        },
        {
            "dbid": 101,
            "value": "Several days",
            "code": "LA6569-3",
            "score_value": "1",
            "selected": False,
            "comment": None,
        },
    ]
    assert all("fill" not in q for q in data["questions"])


def test_mapper_text_and_integer() -> None:
    items = _items(
        QuestionnaireItemFill(questionDbid=10, status="answered", value="nurse", evidence=[_turn()]),
        QuestionnaireItemFill(questionDbid=11, status="answered", value="3", evidence=[_turn()]),
    )
    data = build_fill_command_data(_definition(), items)
    assert data["questions"][0]["responses"][0]["value"] == "nurse"
    assert data["questions"][0]["responses"][0]["selected"] is True
    assert data["questions"][1]["responses"][0]["value"] == "3"
    assert "fill" in data["questions"][0]


def test_mapper_radio_selects_by_dbid_not_position() -> None:
    items = _items(
        QuestionnaireItemFill(questionDbid=12, status="answered", selectedOptionDbid=101, evidence=[_turn()])
    )
    data = build_fill_command_data(_definition(), items)
    assert [r["selected"] for r in data["questions"][2]["responses"]] == [False, True]


def test_mapper_denied_radio_records_chosen_option_and_status() -> None:
    items = _items(QuestionnaireItemFill(questionDbid=12, status="denied", selectedOptionDbid=100, evidence=[_turn()]))
    data = build_fill_command_data(_definition(), items)
    assert [r["selected"] for r in data["questions"][2]["responses"]] == [True, False]
    assert data["questions"][2]["fill"]["status"] == "denied"


def test_mapper_checkbox_affirmed_options() -> None:
    items = _items(
        QuestionnaireItemFill(questionDbid=13, status="answered", selectedOptionDbids=[201], evidence=[_turn()])
    )
    data = build_fill_command_data(_definition(), items)
    assert [r["selected"] for r in data["questions"][3]["responses"]] == [False, True]


def test_mapper_not_assessed_and_blank_leave_no_fill_block() -> None:
    items = _items(
        QuestionnaireItemFill(questionDbid=10, status="not_assessed"),
        QuestionnaireItemFill(questionDbid=11, status="answered", value="   ", evidence=[_turn()]),
        QuestionnaireItemFill(questionDbid=12, status="answered", selectedOptionDbid=None, evidence=[_turn()]),
        QuestionnaireItemFill(questionDbid=13, status="answered", selectedOptionDbids=[], evidence=[_turn()]),
    )
    data = build_fill_command_data(_definition(), items)
    assert all("fill" not in q for q in data["questions"])
    assert all(not r["selected"] for q in data["questions"] for r in q["responses"])


def test_mapper_fill_block_carries_every_evidence_turn() -> None:
    """A bare 'No' is not interpretable without the provider's question, so the card has to
    receive both turns, not just the patient's."""
    items = _items(
        QuestionnaireItemFill(
            questionDbid=12,
            status="denied",
            selectedOptionDbid=100,
            confidence="high",
            rationale="explicit denial",
            evidence=[
                EvidenceTurn(speaker="provider", quote="Any thoughts of harming yourself?", itemId="t1"),
                EvidenceTurn(speaker="patient", quote="No, nothing like that.", itemId="t2"),
            ],
        )
    )
    data = build_fill_command_data(_definition(), items)
    fill = data["questions"][2]["fill"]
    assert [turn["speaker"] for turn in fill["evidence"]] == ["provider", "patient"]
    assert fill["confidence"] == "high"
    assert fill["rationale"] == "explicit denial"


# --- grounding gate ---


def test_grounding_gate_drops_ungrounded() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=7,
        items=[
            QuestionnaireItemFill(questionDbid=12, status="answered", selectedOptionDbid=100, evidence=[_turn("t1")]),
            QuestionnaireItemFill(
                questionDbid=13, status="answered", selectedOptionDbids=[200], evidence=[_turn("nope")]
            ),
        ],
    )
    gated = _apply_grounding_gate(result, _transcript())
    assert [item.question_dbid for item in gated.items] == [12]


def test_grounding_gate_keeps_not_assessed() -> None:
    result = QuestionnaireFillResult(
        questionnaireDbid=7,
        items=[QuestionnaireItemFill(questionDbid=12, status="not_assessed", evidence=[])],
    )
    assert len(_apply_grounding_gate(result, _transcript()).items) == 1


# --- fill_chunk ---


def test_fill_chunk_sends_transcript_and_definition_as_separate_blocks() -> None:
    """Two set_user_prompt calls, not one joined string. Only separate content blocks let
    the transcript be cached while the per-chunk definition varies."""
    client = _client({"questionnaireDbid": 7, "items": []})
    fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert client.set_user_prompt.call_count == 2
    transcript_block = "\n".join(client.set_user_prompt.call_args_list[0].args[0])
    definition_block = "\n".join(client.set_user_prompt.call_args_list[1].args[0])
    assert "TRANSCRIPT" in transcript_block
    assert "QUESTIONNAIRE DEFINITION" in definition_block


def test_fill_chunk_parses_and_grounds() -> None:
    payload = {
        "questionnaireDbid": 7,
        "items": [
            {"questionDbid": 12, "status": "answered", "selectedOptionDbid": 100, "evidence": [_ev("t1")]},
            {"questionDbid": 13, "status": "answered", "selectedOptionDbids": [200], "evidence": [_ev("gone")]},
        ],
    }
    result = fill_chunk("PHQ-9", _questions(), _transcript(), _client(payload))
    assert [item.question_dbid for item in result.items] == [12]


def test_fill_chunk_rate_limit_is_retryable() -> None:
    client = _client({"items": []}, code=HTTPStatus.TOO_MANY_REQUESTS)
    with pytest.raises(FillChunkError) as excinfo:
        fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert excinfo.value.retryable is True


def test_fill_chunk_bad_request_is_not_retryable() -> None:
    """The SDK turns a 30s timeout into BAD_REQUEST, so retrying it just burns another 30
    seconds on the same failure."""
    client = _client({"items": []}, code=HTTPStatus.BAD_REQUEST)
    with pytest.raises(FillChunkError) as excinfo:
        fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert excinfo.value.retryable is False


def test_a_long_transcript_withdraws_the_single_call_shortcut() -> None:
    """On a 47-minute visit, eight questions in one call measured 29s against a 30s wall.

    Latency is not a function of question count alone: a long transcript adds prefill on
    top of the generation the questions drive, so the chunk size has to see the transcript.
    """
    questions = [{"dbid": i} for i in range(SINGLE_CALL_MAX)]
    assert chunk_questions(questions, LONG_TRANSCRIPT_CHARS - 1) == [questions]
    chunks = chunk_questions(questions, LONG_TRANSCRIPT_CHARS)
    assert [len(c) for c in chunks] == [LONG_CHUNK_SIZE, SINGLE_CALL_MAX - LONG_CHUNK_SIZE]
    assert [q for chunk in chunks for q in chunk] == questions


def test_a_long_transcript_leaves_a_short_questionnaire_in_one_call() -> None:
    questions = [{"dbid": i} for i in range(LONG_CHUNK_SIZE)]
    assert chunk_questions(questions, LONG_TRANSCRIPT_CHARS * 10) == [questions]
    assert chunk_questions([], LONG_TRANSCRIPT_CHARS * 10) == []


def test_a_stray_top_level_key_does_not_discard_the_whole_chunk() -> None:
    """THE PRODUCTION FAILURE. Verbatim payload from scribeqa-sandbox, trimmed.

    The model emitted a top-level ``questionDbid`` next to eight correctly grounded
    answers. ``extra="forbid"`` turned that one hallucinated key into a parse error, threw
    all eight answers away, and reported the questionnaire as failed.
    """
    client = _client(
        {
            "questionDbid": 0,
            "questionnaireDbid": 0,
            "items": [
                {"questionDbid": 10, "status": "answered", "value": "electrician", "evidence": [_ev("t1")]},
                {"questionDbid": 11, "status": "answered", "value": "3", "evidence": [_ev("t2")]},
            ],
        }
    )
    result = fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert [item.question_dbid for item in result.items] == [10, 11]


def test_one_malformed_item_does_not_take_its_siblings_down() -> None:
    """A chunk is one request carrying the whole transcript, so salvage what validated."""
    client = _client(
        {
            "items": [
                {"questionDbid": 10, "status": "answered", "value": "electrician", "evidence": [_ev("t1")]},
                {"status": "answered", "value": "no question dbid at all"},
                {"questionDbid": 11, "status": "answered", "value": "3", "evidence": [_ev("t2")]},
            ]
        }
    )
    result = fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert [item.question_dbid for item in result.items] == [10, 11]


def test_nothing_salvageable_still_fails() -> None:
    """Salvage must not turn a genuinely broken response into a silent empty success."""
    client = _client({"items": [{"status": "answered"}]})
    with pytest.raises(FillChunkError) as excinfo:
        fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert excinfo.value.kind == "parse_error"


def test_a_truncated_response_fails_instead_of_reading_as_abstention() -> None:
    """A chunk cut off at max_tokens must not look like a deliberate abstention.

    Anthropic drops the incomplete tool_use arguments when generation stops at
    max_tokens, so the block arrives with an empty ``input``. That parses cleanly as "no
    items", which is exactly what a correct abstention looks like. Confirmed against the
    real API: stop_reason "max_tokens", one tool_use block, input {}.
    """
    client = _client({"items": []})
    client.last_stop_reason = "max_tokens"
    with pytest.raises(FillChunkError) as excinfo:
        fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert excinfo.value.kind == "truncated"
    assert excinfo.value.retryable is False, "the same chunk would truncate again"


def test_a_complete_response_is_not_treated_as_truncated() -> None:
    client = _client({"items": []})
    client.last_stop_reason = "tool_use"
    assert fill_chunk("PHQ-9", _questions(), _transcript(), client).items == []


def test_truncation_does_not_abandon_the_fan_out() -> None:
    """Truncation is a bad answer, not an unavailable API."""
    from hyperscribe.scribe.recommendations.questionnaire_fill import ABORT_KINDS

    assert "truncated" not in ABORT_KINDS


def test_fill_chunk_unparseable_response() -> None:
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK, response="not json", tokens=LlmTokens(prompt=0, generated=0)
    )
    with pytest.raises(FillChunkError):
        fill_chunk("PHQ-9", _questions(), _transcript(), client)


def test_retry_runs_once_for_a_retryable_failure() -> None:
    client = MagicMock()
    client.request.side_effect = [
        LlmResponse(code=HTTPStatus.TOO_MANY_REQUESTS, response="slow down", tokens=LlmTokens(prompt=0, generated=0)),
        LlmResponse(
            code=HTTPStatus.OK,
            response=json.dumps({"questionnaireDbid": 7, "items": []}),
            tokens=LlmTokens(prompt=0, generated=0),
        ),
    ]
    result = fill_chunk_with_retry("PHQ-9", _questions(), _transcript(), client, sleep=lambda _: None)
    assert result.items == []
    assert client.request.call_count == 2


def test_retry_does_not_run_for_a_non_retryable_failure() -> None:
    client = _client({"items": []}, code=HTTPStatus.BAD_REQUEST)
    with pytest.raises(FillChunkError):
        fill_chunk_with_retry("PHQ-9", _questions(), _transcript(), client, sleep=lambda _: None)
    assert client.request.call_count == 1


# --- fill_questionnaires (orchestration) ---


def _long_definition(count: int) -> dict:
    questions = [
        {
            "dbid": 500 + i,
            "label": f"Q{i}",
            "type": ResponseOption.TYPE_RADIO,
            "options": [{"dbid": 900 + i, "value": "Yes", "code": "", "score_value": "1"}],
        }
        for i in range(count)
    ]
    return _definition(questions, scored=False)


def _answer_for(question_dbid: int) -> dict:
    return {
        "questionDbid": question_dbid,
        "status": "answered",
        "selectedOptionDbid": question_dbid + 400,
        "evidence": [_ev("t1")],
    }


def test_fill_questionnaires_warm_up_failure_abandons_the_fan_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A seven-chunk form must not spend seven 30-second timeouts rediscovering one outage."""
    definition = _long_definition(20)
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: definition
    )
    calls = {"n": 0}

    def factory() -> MagicMock:
        calls["n"] += 1
        return _client({"items": []}, code=HTTPStatus.INTERNAL_SERVER_ERROR)

    outcomes, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=factory)
    assert telemetry["chunks"] == 4
    assert telemetry["aborted"] is True
    # The warm-up ran; the retry ran on the same client; nothing else was attempted.
    assert calls["n"] == 1
    assert outcomes[0].error is not None
    assert outcomes[0].drafted == 0


def test_a_parse_error_on_the_warm_up_does_not_abandon_the_fan_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A parse error means the API answered, so the other chunks are still worth running.

    On scribeqa-sandbox one stray key in the first response abandoned every chunk of all
    three questionnaires on the note, and each was reported with the same failure. The
    abort is an outage probe; only an unavailable API should trigger it.
    """
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire",
        lambda dbid: _long_definition(12),
    )
    made: list[MagicMock] = []

    def factory() -> MagicMock:
        # The warm-up returns an unparseable body; every later chunk is fine.
        if not made:
            client = MagicMock()
            client.last_usage = {}
            client.request.return_value = LlmResponse(
                code=HTTPStatus.OK, response="{not json", tokens=LlmTokens(prompt=0, generated=0)
            )
        else:
            client = _client({"items": [_answer_for(506), _answer_for(507)]})
        made.append(client)
        return client

    outcomes, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=factory)
    assert telemetry["aborted"] is False
    assert len(made) == telemetry["chunks"], "every chunk after the warm-up still ran"
    # Partial rather than filled: the later chunks answered, but the warm-up chunk's own
    # questions never got read, and that is exactly what must not be silent.
    assert outcomes[0].status == "partial"
    assert outcomes[0].drafted == 2
    assert len(outcomes[0].unread) == CHUNK_SIZE


def test_an_unavailable_api_on_the_warm_up_still_abandons_the_fan_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """The pair to the test above: a 5xx is an outage, so the abort must still fire."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire",
        lambda dbid: _long_definition(12),
    )
    calls = {"n": 0}

    def factory() -> MagicMock:
        calls["n"] += 1
        return _client({"items": []}, code=HTTPStatus.INTERNAL_SERVER_ERROR)

    _, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=factory)
    assert telemetry["aborted"] is True
    assert calls["n"] == 1


def test_a_parse_error_on_one_questionnaire_leaves_the_others_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three template questionnaires, one bad first response. The other two must fill."""
    definitions = {
        7: _long_definition(2),
        8: _long_definition(2),
        9: _long_definition(2),
    }
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire",
        lambda dbid: definitions[dbid],
    )
    made: list[MagicMock] = []

    def factory() -> MagicMock:
        if not made:
            client = MagicMock()
            client.last_usage = {}
            client.request.return_value = LlmResponse(
                code=HTTPStatus.OK, response="{not json", tokens=LlmTokens(prompt=0, generated=0)
            )
        else:
            client = _client({"items": [_answer_for(500), _answer_for(501)]})
        made.append(client)
        return client

    outcomes, telemetry = fill_questionnaires([7, 8, 9], _transcript(), "key", client_factory=factory)
    assert telemetry["aborted"] is False
    assert [o.status for o in outcomes] == ["failed", "filled", "filled"]


def test_fill_questionnaires_one_failed_chunk_keeps_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = _long_definition(12)
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: definition
    )
    made: list[MagicMock] = []

    def factory() -> MagicMock:
        # Chunk 1 (warm-up) succeeds so the fan-out proceeds; chunk 2 fails.
        if not made:
            client = _client({"questionnaireDbid": 7, "items": [_answer_for(500), _answer_for(501)]})
        else:
            client = _client({"items": []}, code=HTTPStatus.BAD_REQUEST)
        made.append(client)
        return client

    outcomes, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=factory)
    assert telemetry["chunks"] == 2
    assert telemetry["aborted"] is False
    outcome = outcomes[0]
    # The surviving chunk's answers landed, so the questionnaire is not reported as failed.
    assert outcome.drafted == 2
    assert outcome.status == "partial", "not a clean fill: six questions were never read"
    # The failed chunk's questions are present, blank, and editable - and now also named, so
    # the card can distinguish "never read" from "read and declined".
    assert len(outcome.data["questions"]) == 12
    assert all("fill" not in q for q in outcome.data["questions"][CHUNK_SIZE:])
    assert outcome.unread == [q["dbid"] for q in outcome.data["questions"][CHUNK_SIZE:]]


def test_fill_questionnaires_accumulates_cache_telemetry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zero cache reads across a multi-chunk run means the chunking is costing money
    instead of saving it, so the number has to be recorded."""
    definition = _long_definition(12)
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: definition
    )
    seen: list[MagicMock] = []

    def factory() -> MagicMock:
        client = _client({"questionnaireDbid": 7, "items": []})
        client.last_usage = (
            {"input_tokens": 100, "output_tokens": 20, "cache_creation_input_tokens": 900}
            if not seen
            else {"input_tokens": 10, "output_tokens": 20, "cache_read_input_tokens": 900}
        )
        seen.append(client)
        return client

    _, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=factory)
    assert telemetry["cache_write_tokens"] == 900
    assert telemetry["cache_read_tokens"] == 900
    assert telemetry["output_tokens"] == 40


def test_fill_questionnaires_unloadable_questionnaire_reports_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def loader(dbid: int) -> dict:
        if dbid == 99:
            raise ValueError("no such questionnaire")
        return _definition()

    monkeypatch.setattr("hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", loader)
    outcomes, _ = fill_questionnaires(
        [99, 7], _transcript(), "key", client_factory=lambda: _client({"questionnaireDbid": 7, "items": []})
    )
    assert outcomes[0].error == "load_failed"
    assert outcomes[0].data is None
    assert outcomes[1].data is not None


def test_fill_chunk_treats_a_raised_request_as_retryable() -> None:
    """A transport blowing up is not the same as the API refusing, so it earns the retry."""
    client = MagicMock()
    client.request.side_effect = RuntimeError("socket closed")
    with pytest.raises(FillChunkError) as excinfo:
        fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert excinfo.value.retryable is True


def test_fill_questionnaires_single_chunk_failure_is_not_an_abort(monkeypatch: pytest.MonkeyPatch) -> None:
    """With one chunk there is no fan-out to abandon, so the run reports a plain failure
    rather than the outage-probe abort."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    outcomes, telemetry = fill_questionnaires(
        [7], _transcript(), "key", client_factory=lambda: _client({"items": []}, code=HTTPStatus.BAD_REQUEST)
    )
    assert telemetry["chunks"] == 1
    assert telemetry["aborted"] is False
    assert outcomes[0].error is not None
    # The card still receives every question, blank and editable.
    assert len(outcomes[0].data["questions"]) == 4


def test_fill_questionnaires_spans_several_questionnaires(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batching is the point: one warm cache shared across every questionnaire on the note."""
    definitions = {7: _definition(), 8: _definition(_questions()[:2], scored=False)}
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: definitions[dbid]
    )
    payload = {
        "questionnaireDbid": 7,
        "items": [{"questionDbid": 10, "status": "answered", "value": "nurse", "evidence": [_ev("t1")]}],
    }
    outcomes, telemetry = fill_questionnaires([7, 8], _transcript(), "key", client_factory=lambda: _client(payload))
    assert telemetry["chunks"] == 2
    assert [o.questionnaire_dbid for o in outcomes] == [7, 8]
    assert all(o.error is None for o in outcomes)


@patch("hyperscribe.scribe.recommendations.questionnaire_fill.QuestionnaireCommand")
def test_resolve_definition_is_the_one_shape_three_call_sites_share(mock_command: MagicMock) -> None:
    """/questionnaire-details, /visit-templates and the fill all render from this. They
    used to build it separately and drifted: the fill's copy dropped code and score_value,
    which is exactly why a filled PHQ-9 could not compute a score."""
    option = SimpleNamespace(dbid=100, name="Not at all", code="LA6568-5", value=0)
    question = SimpleNamespace(id="12", label="Interest?", type=ResponseOption.TYPE_RADIO, options=[option])
    mock_command.return_value = SimpleNamespace(questions=[question])
    q_obj = SimpleNamespace(id="uuid-1", dbid=7, name="PHQ-9", scoring_function_name="sum")

    definition = resolve_questionnaire_definition(q_obj)

    assert definition["questionnaire_dbid"] == 7
    assert definition["questionnaire_name"] == "PHQ-9"
    assert definition["is_scored"] is True
    assert definition["questions"] == [
        {
            "dbid": 12,
            "label": "Interest?",
            "type": ResponseOption.TYPE_RADIO,
            # score_value "0" survives as a string: integer 0 means "Not at all" and a
            # falsy-coerce would silently destroy a real clinical score.
            "options": [{"dbid": 100, "value": "Not at all", "code": "LA6568-5", "score_value": "0"}],
        }
    ]


@patch("hyperscribe.scribe.recommendations.questionnaire_fill.QuestionnaireCommand")
def test_resolve_definition_marks_an_unscored_questionnaire(mock_command: MagicMock) -> None:
    mock_command.return_value = SimpleNamespace(questions=[])
    q_obj = SimpleNamespace(id="uuid-1", dbid=8, name="Social history", scoring_function_name="")
    definition = resolve_questionnaire_definition(q_obj)
    assert definition["is_scored"] is False
    assert definition["scoring_function_name"] == ""


# --- outcome status ---------------------------------------------------------
#
# The point of `status` is that `drafted == 0` on its own is ambiguous: it means both
# "read the transcript and nothing supported an answer" (the grounding rule working) and
# "never ran" (a bug). These pin the boundary between them.


def _all_not_assessed() -> dict:
    """What a real abstention looks like: the model considered every question and declined."""
    return {
        "questionnaireDbid": 7,
        "items": [{"questionDbid": q["dbid"], "status": "not_assessed"} for q in _questions()],
    }


def test_status_abstained_when_the_transcript_covers_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    outcomes, _ = fill_questionnaires([7], _transcript(), "key", client_factory=lambda: _client(_all_not_assessed()))
    outcome = outcomes[0]
    assert outcome.status == "abstained"
    assert outcome.error is None
    assert outcome.drafted == 0
    assert outcome.total == 4
    # It considered every question, which is what separates this from a parse problem.
    assert outcome.assessed == 4
    # The card still receives the whole questionnaire, blank and editable.
    assert len(outcome.data["questions"]) == 4


def test_status_failed_is_distinguished_from_abstained(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both have drafted == 0. Conflating them is the bug this change exists to fix."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    outcomes, _ = fill_questionnaires(
        [7], _transcript(), "key", client_factory=lambda: _client({"items": []}, code=HTTPStatus.BAD_REQUEST)
    )
    assert outcomes[0].status == "failed"
    assert outcomes[0].error is not None


def test_status_filled_when_anything_landed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    payload = {
        "questionnaireDbid": 7,
        "items": [{"questionDbid": 10, "status": "answered", "value": "nurse", "evidence": [_ev("t1")]}],
    }
    outcomes, _ = fill_questionnaires([7], _transcript(), "key", client_factory=lambda: _client(payload))
    assert outcomes[0].status == "filled"
    assert (outcomes[0].drafted, outcomes[0].total) == (1, 4)


def test_status_no_transcript_is_not_a_failure() -> None:
    """Returning [] here made the frontend report 'Fill failed'. Nothing failed."""
    outcomes, telemetry = fill_questionnaires([7, 8], Transcript(items=[]), "key")
    assert [o.status for o in outcomes] == ["no_transcript", "no_transcript"]
    assert all(o.error is None for o in outcomes)
    assert telemetry["chunks"] == 0


def test_no_questionnaires_requested_is_a_caller_error_not_an_outcome() -> None:
    assert fill_questionnaires([], _transcript(), "key")[0] == []


def test_status_partial_when_one_chunk_failed_but_another_landed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A partial success is not a clean fill, and the difference has to reach the card.

    The surviving answers are real and grounded, so the questionnaire is not a failure. But
    the questions in the failed chunk were never read, and reporting the whole thing as
    ``filled`` left them sitting blank next to copy that said the model had considered them
    and declined. Silence looked like a finding.
    """
    definition = _long_definition(12)
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: definition
    )
    made: list[MagicMock] = []

    def factory() -> MagicMock:
        client = (
            _client({"questionnaireDbid": 7, "items": [_answer_for(500)]})
            if not made
            else _client({"items": []}, code=HTTPStatus.BAD_REQUEST)
        )
        made.append(client)
        return client

    outcomes, _ = fill_questionnaires([7], _transcript(), "key", client_factory=factory)
    outcome = outcomes[0]
    assert outcome.status == "partial"
    assert outcome.drafted == 1, "the surviving answer landed"
    # The failed chunk was questions 506..511, so those are the ones never read.
    assert outcome.unread == [506, 507, 508, 509, 510, 511]
    assert outcome.error is not None, "the cause survives into the audit row"


def test_assessed_is_zero_when_the_model_returns_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Looks like an abstention from outside, but points at a schema or parse problem
    rather than an honest one, which is why the audit row carries the count."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    outcomes, _ = fill_questionnaires(
        [7], _transcript(), "key", client_factory=lambda: _client({"questionnaireDbid": 7, "items": []})
    )
    assert outcomes[0].status == "abstained"
    assert outcomes[0].assessed == 0


# --- failure kinds ----------------------------------------------------------


@pytest.mark.parametrize(
    "code, expected",
    [
        (HTTPStatus.REQUEST_TIMEOUT, "timeout"),
        (HTTPStatus.TOO_MANY_REQUESTS, "rate_limited"),
        (HTTPStatus.SERVICE_UNAVAILABLE, "connection_error"),
        (HTTPStatus.BAD_REQUEST, "bad_request"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "server_error"),
        (HTTPStatus.NOT_FOUND, "client_error"),
    ],
)
def test_failure_kind_names_the_cause(code: HTTPStatus, expected: str) -> None:
    assert failure_kind(code) == expected


def test_a_timeout_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 30s ceiling is fixed, so a second attempt burns another 30 seconds on the same
    too-large chunk."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    client = _client({}, code=HTTPStatus.REQUEST_TIMEOUT)
    outcomes, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=lambda: client)

    assert client.request.call_count == 1
    assert outcomes[0].status == "failed"
    assert telemetry["failures"] == {"timeout": 1}


def test_a_connection_error_is_retried_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """This is the behaviour change: while every transport failure was a 400, a transient
    blip shared the timeout's bucket and was never retried."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire", lambda dbid: _definition()
    )
    monkeypatch.setattr("hyperscribe.scribe.recommendations.questionnaire_fill.time.sleep", lambda _: None)
    client = _client({}, code=HTTPStatus.SERVICE_UNAVAILABLE)
    _, telemetry = fill_questionnaires([7], _transcript(), "key", client_factory=lambda: client)

    assert client.request.call_count == 2
    assert telemetry["failures"] == {"connection_error": 1}


def test_the_run_records_which_kind_of_failure_it_hit(monkeypatch: pytest.MonkeyPatch) -> None:
    """One audit row should answer 'why did this run fail' without reading chunk logs."""
    monkeypatch.setattr(
        "hyperscribe.scribe.recommendations.questionnaire_fill.load_questionnaire",
        lambda dbid: _long_definition(12),
    )
    monkeypatch.setattr("hyperscribe.scribe.recommendations.questionnaire_fill.time.sleep", lambda _: None)
    _, telemetry = fill_questionnaires(
        [7], _transcript(), "key", client_factory=lambda: _client({}, code=HTTPStatus.REQUEST_TIMEOUT)
    )
    assert telemetry["failures"] == {"timeout": 1}
    # The warm-up doubles as the outage probe, so the fan-out never ran.
    assert telemetry["aborted"] is True


def test_a_parse_failure_is_named_separately() -> None:
    client = MagicMock()
    client.last_usage = {}
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK, response="not json", tokens=LlmTokens(prompt=0, generated=0)
    )
    with pytest.raises(FillChunkError) as excinfo:
        fill_chunk("PHQ-9", _questions(), _transcript(), client)
    assert excinfo.value.kind == "parse_error"
