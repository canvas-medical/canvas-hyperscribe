import json
from unittest.mock import patch, call

import pytest
from logger import log

from hyperscribe.handlers.llms.llm_anthropic import LlmAnthropic
from hyperscribe.handlers.structures.http_response import HttpResponse


def test_add_audio():
    tested = LlmAnthropic("anthropicKey", "theModel")
    with pytest.raises(Exception) as e:
        _ = tested.add_audio(b"audio", "format")
    expected = "NotImplementedError"
    assert e.typename == expected


def test_to_dict():
    tested = LlmAnthropic("anthropicKey", "theModel")
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])

    #
    result = tested.to_dict()
    expected = {
        "model": "theModel",
        "temperature": 0.0,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "line 1\nline 2\nline 3"},
                    {"type": "text", "text": "line 4\nline 5\nline 6"},
                ],
            },
        ],
    }
    assert result == expected

    # with an exchange with the model
    tested.set_model_prompt(["line 7", "line 8"])
    tested.set_user_prompt(["line 9", "line 10"])
    result = tested.to_dict()
    expected = {
        "model": "theModel",
        "temperature": 0.0,
        "max_tokens": 8192,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "line 1\nline 2\nline 3"},
                    {"type": "text", "text": "line 4\nline 5\nline 6"},
                ],
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "line 7\nline 8"},
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "line 9\nline 10"},
                ],
            },
        ],
    }
    assert result == expected


@patch("hyperscribe.handlers.llms.llm_anthropic.requests_post")
@patch.object(log, "info")
@patch.object(LlmAnthropic, "to_dict")
def test_request(to_dict, info, requests_post):
    def reset_mocks():
        to_dict.reset_mock()
        info.reset_mock()
        requests_post.reset_mock()

    response = type("Response", (), {
        "status_code": 202,
        "text": json.dumps({
            "content": [
                {"text": "\n".join([
                    '```json',
                    '["line 1","line 2","line 3"]',
                    '```',
                    '',
                ])},
            ],
        }),
    })()

    # error
    to_dict.side_effect = [{"key": "value"}]
    requests_post.side_effect = [response]

    tested = LlmAnthropic("apiKey", "theModel")
    result = tested.request()
    expected = HttpResponse(
        code=202,
        response='{"content": [{"text": "```json\\n[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n```\\n"}]}',
    )
    assert result == expected

    calls = [call()]
    assert to_dict.mock_calls == calls
    assert info.mock_calls == []
    calls = [call(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": "apiKey",
        },
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()

    # no error
    response.status_code = 200
    # -- with log
    to_dict.side_effect = [{"key": "valueA"}, {"key": "valueB"}]
    requests_post.side_effect = [response]

    tested = LlmAnthropic("apiKey", "theModel")
    result = tested.request(True)
    expected = HttpResponse(code=200, response='```json\n["line 1","line 2","line 3"]\n```\n')
    assert result == expected

    calls = [
        call(),
        call(),
    ]
    assert to_dict.mock_calls == calls
    calls = [
        call("***** CHAT STARTS ******"),
        call('{\n  "key": "valueB"\n}'),
        call('response code: >200<'),
        call('{"content": [{"text": "```json\\n[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n```\\n"}]}'),
        call("****** CHAT ENDS *******"),
    ]
    assert info.mock_calls == calls
    calls = [call(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": "apiKey",
        },
        params={},
        data='{"key": "valueA"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
    # -- without log
    to_dict.side_effect = [{"key": "value"}]
    requests_post.side_effect = [response]

    tested = LlmAnthropic("apiKey", "theModel")
    result = tested.request()
    expected = HttpResponse(code=200, response='```json\n["line 1","line 2","line 3"]\n```\n')
    assert result == expected

    calls = [call()]
    assert to_dict.mock_calls == calls
    assert info.mock_calls == []
    calls = [call(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": "apiKey",
        },
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
