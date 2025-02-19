import json
from unittest.mock import patch, call

import pytest
from logger import log

from commander.protocols.llms.llm_base import LlmBase
from commander.protocols.structures.json_extract import JsonExtract


def test___init__():
    tested = LlmBase("apiKey", "theModel")
    assert tested.api_key == "apiKey"
    assert tested.model == "theModel"
    assert tested.temperature == 0.0
    assert tested.system_prompt == []
    assert tested.user_prompt == []
    assert tested.audios == []


def test_set_system_prompt():
    tested = LlmBase("apiKey", "theModel")
    assert tested.system_prompt == []
    tested.set_system_prompt(["line 1", "line 2"])
    result = tested.system_prompt
    expected = ["line 1", "line 2"]
    assert result == expected


def test_set_user_prompt():
    tested = LlmBase("apiKey", "theModel")
    assert tested.user_prompt == []
    tested.set_user_prompt(["line 1", "line 2"])
    result = tested.user_prompt
    expected = ["line 1", "line 2"]
    assert result == expected


def test_chat():
    tested = LlmBase("apiKey", "theModel")
    with pytest.raises(Exception) as e:
        _ = tested.chat()
    expected = "NotImplementedError"
    assert e.typename == expected


@patch.object(LlmBase, "chat")
def test_single_conversation(chat):
    def reset_mocks():
        chat.reset_mock()

    system_prompt = ["theSystemPrompt"]
    user_prompt = ["theUserPrompt"]
    tested = LlmBase("theApiKey", "theModel")

    # without error
    chat.side_effect = [JsonExtract(error="theError", has_error=False, content=["theContent"])]
    result = tested.single_conversation(system_prompt, user_prompt)
    assert result == ["theContent"]

    calls = [call()]
    assert chat.mock_calls == calls
    reset_mocks()

    # with error
    chat.side_effect = [JsonExtract(error="theError", has_error=True, content=["theContent"])]
    result = tested.single_conversation(system_prompt, user_prompt)
    assert result == []

    calls = [call()]
    assert chat.mock_calls == calls
    reset_mocks()


@patch.object(log, "info")
def test_extract_json_from(info):
    def reset_mocks():
        info.reset_mock()

    tested = LlmBase
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
    result = tested.extract_json_from(content)
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
    # -- one JSON
    content = "\n".join([
        "response:",
        "```json",
        json.dumps(["item1", "item2"]),
        "```",
        "",
        "end.",
    ])
    result = tested.extract_json_from(content)
    expected = JsonExtract(
        error="",
        has_error=False,
        content=["item1", "item2"],
    )
    assert result == expected

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
    result = tested.extract_json_from(content)
    expected = JsonExtract(
        error="Expecting ',' delimiter: line 1 column 9 (char 8)",
        has_error=True,
        content=[],
    )
    assert result == expected
    # -- no JSON
    content = "\n".join([
        "response:",
        json.dumps(["item1", "item2"]),
        "",
        "end.",
    ])
    result = tested.extract_json_from(content)
    expected = JsonExtract(
        error='No JSON markdown found',
        has_error=True,
        content=[],
    )
    assert result == expected
