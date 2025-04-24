import json
from unittest.mock import patch, call, MagicMock

import pytest

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.llm_turn import LlmTurn
from tests.helper import is_constant


def test_constants():
    tested = LlmBase
    constants = {
        "ROLE_SYSTEM": "system",
        "ROLE_USER": "user",
        "ROLE_MODEL": "model",
    }
    assert is_constant(tested, constants)


def test___init__():
    memory_log = MagicMock()
    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    assert memory_log.mock_calls == []
    assert tested.memory_log == memory_log
    assert tested.api_key == "apiKey"
    assert tested.model == "theModel"
    assert tested.with_audit == False
    assert tested.temperature == 0.0
    assert tested.prompts == []
    assert tested.audios == []


def test_set_system_prompt():
    memory_log = MagicMock()
    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    assert tested.prompts == []
    #
    tested.set_system_prompt(["line 1", "line 2"])
    result = tested.prompts
    expected = [LlmTurn(role="system", text=["line 1", "line 2"])]
    assert result == expected
    assert memory_log.mock_calls == []
    #
    tested.set_system_prompt(["line 3"])
    result = tested.prompts
    expected = [LlmTurn(role="system", text=["line 3"])]
    assert result == expected
    assert memory_log.mock_calls == []
    #
    tested.prompts = [LlmTurn(role="user", text=["line 1", "line 2"])]
    tested.set_system_prompt(["line 3"])
    result = tested.prompts
    expected = [
        LlmTurn(role="system", text=["line 3"]),
        LlmTurn(role="user", text=["line 1", "line 2"]),
    ]
    assert result == expected
    assert memory_log.mock_calls == []


def test_set_user_prompt():
    memory_log = MagicMock()
    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    assert tested.prompts == []
    tested.set_user_prompt(["line 1", "line 2"])
    result = tested.prompts
    expected = [LlmTurn(role="user", text=["line 1", "line 2"])]
    assert result == expected
    assert memory_log.mock_calls == []


def test_set_model_prompt():
    memory_log = MagicMock()
    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    assert tested.prompts == []
    tested.set_model_prompt(["line 1", "line 2"])
    result = tested.prompts
    expected = [LlmTurn(role="model", text=["line 1", "line 2"])]
    assert result == expected
    assert memory_log.mock_calls == []


def test_add_audio():
    memory_log = MagicMock()
    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    with pytest.raises(NotImplementedError):
        _ = tested.add_audio(b"audio", "format")
    assert memory_log.mock_calls == []


def test_request():
    memory_log = MagicMock()
    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    with pytest.raises(NotImplementedError):
        _ = tested.request()
    assert memory_log.mock_calls == []


@patch.object(LlmBase, "request")
def test_attempt_requests(request):
    memory_log = MagicMock()

    def reset_mocks():
        request.reset_mock()

    tested = LlmBase(memory_log, "apiKey", "theModel", False)

    # one error
    request.side_effect = [
        HttpResponse(code=501, response="some response1"),
        HttpResponse(code=200, response="some response2"),
    ]
    result = tested.attempt_requests(3)
    expected = HttpResponse(code=200, response="some response2")
    assert result == expected
    calls = [call(), call()]
    assert request.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()

    # too many errors
    request.side_effect = [
        HttpResponse(code=501, response="some response1"),
        HttpResponse(code=501, response="some response2"),
        HttpResponse(code=501, response="some response3"),
        HttpResponse(code=200, response="some response4"),
    ]
    result = tested.attempt_requests(3)
    expected = HttpResponse(code=429, response="Http error: max attempts (3) exceeded")
    assert result == expected
    calls = [call(), call(), call()]
    assert request.mock_calls == calls
    calls = [call.log('error: Http error: max attempts (3) exceeded')]
    assert memory_log.mock_calls == calls
    reset_mocks()


@patch.object(LlmBase, "extract_json_from")
@patch.object(LlmBase, "attempt_requests")
def test_chat(attempt_requests, extract_json_from):
    memory_log = MagicMock()

    def reset_mocks():
        attempt_requests.reset_mock()
        extract_json_from.reset_mock()

    tested = LlmBase(memory_log, "apiKey", "theModel", False)
    assert tested.prompts == []

    # http error
    attempt_requests.side_effect = [HttpResponse(code=429, response="max attempts (3) exceeded")]
    extract_json_from.side_effect = []
    result = tested.chat([])
    expected = JsonExtract(has_error=True, error="max attempts (3) exceeded", content=[])
    assert result == expected

    assert tested.prompts == []

    calls = [call(3)]
    assert attempt_requests.mock_calls == calls
    assert extract_json_from.mock_calls == []
    calls = [
        call.log('-- CHAT BEGINS --'),
        call.log('--- CHAT ENDS ---'),
        call.store_so_far(),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # no http error
    # -- one json error
    attempt_requests.side_effect = [
        HttpResponse(code=200, response="response1:\nline1\nline2"),
        HttpResponse(code=200, response="response2:\nline3\nline4"),
    ]
    extract_json_from.side_effect = [
        JsonExtract(has_error=True, error="some error1", content=["error 1"]),
        JsonExtract(has_error=False, error="no error", content=["line1", "line2"]),
    ]
    result = tested.chat([])
    expected = JsonExtract(has_error=False, error="no error", content=["line1", "line2"])
    assert result == expected

    exp_prompts = [
        LlmTurn(role='model', text=['response1:', 'line1', 'line2']),
        LlmTurn(role='user', text=[
            'Your previous response has the following errors:',
            '```text',
            'some error1',
            '```',
            '',
            'Please, correct your answer following rigorously the initial request and the mandatory response format.',
        ]),
    ]
    assert tested.prompts == exp_prompts
    tested.prompts = []

    calls = [
        call(3),
        call(3),
    ]
    assert attempt_requests.mock_calls == calls
    calls = [
        call('response1:\nline1\nline2', []),
        call('response2:\nline3\nline4', []),
    ]
    assert extract_json_from.mock_calls == calls
    calls = [
        call.log('-- CHAT BEGINS --'),
        call.log('--- CHAT ENDS ---'),
        call.store_so_far(),
        call.log('-- CHAT BEGINS --'),
        call.log('result->>'),
        call.log('[\n  "line1",\n  "line2"\n]'),
        call.log('<<-'),
        call.log('--- CHAT ENDS ---'),
        call.store_so_far(),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
    # -- too many json error
    attempt_requests.side_effect = [
        HttpResponse(code=200, response="response1:\nline1\nline2"),
        HttpResponse(code=200, response="response2:\nline3\nline4"),
        HttpResponse(code=200, response="response3:\nline5\nline6"),
        HttpResponse(code=200, response="response4:\nline7\nline8"),
    ]
    extract_json_from.side_effect = [
        JsonExtract(has_error=True, error="some error1", content=["error 1"]),
        JsonExtract(has_error=True, error="some error2", content=["error 2"]),
        JsonExtract(has_error=True, error="some error3", content=["error 3"]),
    ]
    result = tested.chat([])
    expected = JsonExtract(has_error=True, error="JSON incorrect: max attempts (3) exceeded", content=[])
    assert result == expected

    exp_prompts = [
        LlmTurn(role='model', text=['response1:', 'line1', 'line2']),
        LlmTurn(role='user', text=[
            'Your previous response has the following errors:',
            '```text',
            'some error1',
            '```',
            '',
            'Please, correct your answer following rigorously the initial request and the mandatory response format.',
        ]),
        LlmTurn(role='model', text=['response2:', 'line3', 'line4']),
        LlmTurn(role='user', text=[
            'Your previous response has the following errors:',
            '```text',
            'some error2',
            '```',
            '',
            'Please, correct your answer following rigorously the initial request and the mandatory response format.',
        ]),
        LlmTurn(role='model', text=['response3:', 'line5', 'line6']),
        LlmTurn(role='user', text=[
            'Your previous response has the following errors:',
            '```text',
            'some error3',
            '```',
            '',
            'Please, correct your answer following rigorously the initial request and the mandatory response format.',
        ]),
    ]
    assert tested.prompts == exp_prompts
    tested.prompts = []

    calls = [
        call(3),
        call(3),
        call(3),
    ]
    assert attempt_requests.mock_calls == calls
    calls = [
        call('response1:\nline1\nline2', []),
        call('response2:\nline3\nline4', []),
        call('response3:\nline5\nline6', []),
    ]
    assert extract_json_from.mock_calls == calls
    calls = [
        call.log('-- CHAT BEGINS --'),
        call.log('--- CHAT ENDS ---'),
        call.store_so_far(),
        call.log('-- CHAT BEGINS --'),
        call.log('result->>'),
        call.log('[\n  "line1",\n  "line2"\n]'),
        call.log('<<-'),
        call.log('--- CHAT ENDS ---'),
        call.store_so_far(),
        call.log('-- CHAT BEGINS --'),
        call.log('error: JSON incorrect: max attempts (3) exceeded'),
        call.log('--- CHAT ENDS ---'),
        call.store_so_far(),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()


@patch.object(LlmBase, "set_user_prompt")
@patch.object(LlmBase, "set_system_prompt")
@patch.object(LlmBase, "chat")
def test_single_conversation(chat, set_system_prompt, set_user_prompt):
    memory_log = MagicMock()

    def reset_mocks():
        chat.reset_mock()
        set_system_prompt.reset_mock()
        set_user_prompt.reset_mock()
        memory_log.reset_mock()

    system_prompt = ["theSystemPrompt"]
    user_prompt = ["theUserPrompt"]
    schemas = ["schema1", "schema2"]
    audit_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "the referenced key",
                },
                "keyPath": {
                    "type": "string",
                    "description": "the JSON path of the referenced key from the root if there is more than one object",
                },
                "rationale": {
                    "type": "string",
                    "description": "the rationale of the provided value",
                },
            },
            "required": ["key", "rationale"],
            "additionalProperties": False,
        }
    }
    tested = LlmBase(memory_log, "theApiKey", "theModel", True)

    # without error
    # -- no instruction, list
    chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[["theContent"]])]
    result = tested.single_conversation(system_prompt, user_prompt, schemas, None)
    assert result == ["theContent"]

    calls = [call(["schema1", "schema2"])]
    assert chat.mock_calls == calls
    calls = [call(system_prompt)]
    assert set_system_prompt.mock_calls == calls
    calls = [call(user_prompt)]
    assert set_user_prompt.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()
    # -- no instruction, not list
    chat.side_effect = [JsonExtract(error="theError", has_error=False, content=["one", "two"])]
    result = tested.single_conversation(system_prompt, user_prompt, schemas, None)
    assert result == ["one", "two"]

    calls = [call(["schema1", "schema2"])]
    assert chat.mock_calls == calls
    calls = [call(system_prompt)]
    assert set_system_prompt.mock_calls == calls
    calls = [call(user_prompt)]
    assert set_user_prompt.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()
    # -- with instruction
    # -- -- with audit
    tested = LlmBase(memory_log, "theApiKey", "theModel", True)
    instruction = Instruction(uuid="theUuid", instruction="Second", information="theInformation", is_new=False, is_updated=True, audits=[])
    chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[["theContent"], ["theAudit"]])]
    result = tested.single_conversation(system_prompt, user_prompt, schemas, instruction)
    assert result == ["theContent"]
    assert instruction.audits == [
        '-------------',
        '[\n'
        ' [\n'
        '  "theContent"\n'
        ' ],\n'
        ' [\n'
        '  "theAudit"\n'
        ' ]\n'
        ']',
    ]
    calls = [call(["schema1", "schema2", audit_schema])]
    assert chat.mock_calls == calls
    calls = [call(system_prompt)]
    assert set_system_prompt.mock_calls == calls
    calls = [call([
        'theUserPrompt',
        'As a following step, provide the rationale of each and every value you have provided.',
        'Provide the reasoning behind each and every value you provided, your response  in an additional JSON has to follow this JSON Schema:',
        '```json',
        '{\n "$schema": "http://json-schema.org/draft-07/schema#",\n'
        ' "type": "array",\n'
        ' "items": {\n'
        '  "type": "object",\n'
        '  "properties": {\n'
        '   "key": {\n    "type": "string",\n    "description": "the referenced key"\n   },\n'
        '   "keyPath": {\n'
        '    "type": "string",\n'
        '    "description": "the JSON path of the referenced key from the root if there is more than one object"\n'
        '   },\n'
        '   "rationale": {\n    "type": "string",\n    "description": "the rationale of the provided value"\n   }\n'
        '  },\n'
        '  "required": [\n   "key",\n   "rationale"\n  ],\n'
        '  "additionalProperties": false\n'
        ' }\n}',
        '```',
        '',
    ])]
    assert set_user_prompt.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()
    # -- -- with no audit
    tested = LlmBase(memory_log, "theApiKey", "theModel", False)
    instruction = Instruction(uuid="theUuid", instruction="Second", information="theInformation", is_new=False, is_updated=True, audits=[])
    chat.side_effect = [JsonExtract(error="theError", has_error=False, content=[["theContent"], ["theAudit"]])]
    result = tested.single_conversation(system_prompt, user_prompt, schemas, instruction)
    assert result == [["theContent"], ["theAudit"]]
    assert instruction.audits == []
    calls = [call(["schema1", "schema2"])]
    assert chat.mock_calls == calls
    calls = [call(system_prompt)]
    assert set_system_prompt.mock_calls == calls
    calls = [call(['theUserPrompt'])]
    assert set_user_prompt.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()

    # with error
    chat.side_effect = [JsonExtract(error="theError", has_error=True, content=[["theContent"]])]
    result = tested.single_conversation(system_prompt, user_prompt, schemas, None)
    assert result == []

    calls = [call(["schema1", "schema2"])]
    assert chat.mock_calls == calls
    calls = [call(system_prompt)]
    assert set_system_prompt.mock_calls == calls
    calls = [call(user_prompt)]
    assert set_user_prompt.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()


def test_json_validator():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "properties": {
                "a": {"type": "integer", "minimum": 5},
                "b": {"type": "string", "minLength": 2},
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    }

    tests = [
        ([], "[] should be non-empty"),
        ([{"a": 7}], "'b' is a required property, in path [0]"),
        ([{"b": "xy"}], "'a' is a required property, in path [0]"),
        ([{"a": 7, "b": ""}], "'' is too short, in path [0, 'b']"),
        ([{"a": 3, "b": "xy"}], "3 is less than the minimum of 5, in path [0, 'a']"),
        ([{"a": 7, "b": "xy"}], ""),
    ]
    tested = LlmBase
    for response, expected in tests:
        result = tested.json_validator(response, schema)
        assert result == expected, f"---> {response}"


@patch.object(LlmBase, "json_validator")
def test_extract_json_from(json_validator):
    def reset_mocks():
        json_validator.reset_mock()

    tested = LlmBase
    # --> with no schema provided <--
    json_validator.side_effect = []
    # no error
    # -- multiple JSON
    content = "\n".join([
        "response:",
        "```json",
        json.dumps(["item1", "item2"]),
        "```",
        "",
        "```json",
        json.dumps(["item3"]),
        "```",
        "",
        "```json",
        json.dumps(["item4"]),
        "```",
        "",
        "end.",
    ])
    result = tested.extract_json_from(content, [])
    expected = JsonExtract(
        error="",
        has_error=False,
        content=[
            ["item1", "item2"],
            ["item3"],
            ["item4"],
        ],
    )
    assert result == expected
    assert json_validator.mock_calls == []

    # error
    # -- JSON with error
    content = "\n".join([
        "response:",
        "```json",
        json.dumps(["item1", "item2"]),
        "```",
        "",
        "```json",
        "[\"item3\"",
        "```",
        "",
        "```json",
        json.dumps(["item4"]),
        "```",
        "",
        "end.",
    ])
    result = tested.extract_json_from(content, [])
    expected = JsonExtract(
        error="Expecting ',' delimiter: line 1 column 9 (char 8)",
        has_error=True,
        content=[],
    )
    assert result == expected
    assert json_validator.mock_calls == []
    # -- no JSON
    content = "\n".join([
        "response:",
        json.dumps(["item1", "item2"]),
        "",
        "end.",
    ])
    result = tested.extract_json_from(content, [])
    expected = JsonExtract(
        error='No JSON markdown found',
        has_error=True,
        content=[],
    )
    assert result == expected
    assert json_validator.mock_calls == []

    # --> with schema provided <--
    content = "\n".join([
        "response:",
        "```json",
        json.dumps(["item1", "item2"]),
        "```",
        "",
        "```json",
        json.dumps(["item3"]),
        "```",
        "",
        "```json",
        json.dumps(["item4"]),
        "```",
        "",
        "end.",
    ])
    # no error
    json_validator.side_effect = ["", "", ""]
    result = tested.extract_json_from(content, ["schemaA", "schemaB", "schemaC", "schemaD"])
    expected = JsonExtract(
        error="",
        has_error=False,
        content=[
            ["item1", "item2"],
            ["item3"],
            ["item4"],
        ],
    )
    assert result == expected
    calls = [
        call(['item1', 'item2'], 'schemaA'),
        call(['item3'], 'schemaB'),
        call(['item4'], 'schemaC'),
    ]
    assert json_validator.mock_calls == calls
    reset_mocks()
    # with error
    json_validator.side_effect = ["", "this is an error", ""]
    result = tested.extract_json_from(content, ["schemaA", "schemaB", "schemaC", "schemaD"])
    expected = JsonExtract(error='in the JSON #2:this is an error', has_error=True, content=[])
    assert result == expected
    calls = [
        call(['item1', 'item2'], 'schemaA'),
        call(['item3'], 'schemaB'),
    ]
    assert json_validator.mock_calls == calls
    reset_mocks()
