import json
from unittest.mock import patch, call, MagicMock

import pytest

from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts


def test_support_speaker_identification():
    memory_log = MagicMock()
    tested = LlmAnthropic(memory_log, "anthropicKey", "theModel", False)
    result = tested.support_speaker_identification()
    assert result is True


def test_add_audio():
    memory_log = MagicMock()
    tested = LlmAnthropic(memory_log, "anthropicKey", "theModel", False)
    with pytest.raises(Exception) as e:
        _ = tested.add_audio(b"audio", "format")
    expected = "NotImplementedError"
    assert e.typename == expected
    assert memory_log.mock_calls == []


def test_to_dict():
    memory_log = MagicMock()
    tested = LlmAnthropic(memory_log, "anthropicKey", "theModel", False)
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
    assert memory_log.mock_calls == []

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
            {"role": "assistant", "content": [{"type": "text", "text": "line 7\nline 8"}]},
            {"role": "user", "content": [{"type": "text", "text": "line 9\nline 10"}]},
        ],
    }
    assert result == expected
    assert memory_log.mock_calls == []


@patch("hyperscribe.llms.llm_anthropic.requests_post")
@patch.object(LlmAnthropic, "to_dict")
def test_request(to_dict, requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        to_dict.reset_mock()
        requests_post.reset_mock()
        memory_log.reset_mock()

    response = type(
        "Response",
        (),
        {
            "status_code": 202,
            "text": json.dumps(
                {
                    "content": [{"text": "\n".join(["```json", '["line 1","line 2","line 3"]', "```", ""])}],
                    "usage": {"input_tokens": 137, "output_tokens": 43},
                },
            ),
        },
    )()

    # error
    to_dict.side_effect = [{"key": "valueX"}, {"key": "valueY"}]
    requests_post.side_effect = [response]

    tested = LlmAnthropic(memory_log, "apiKey", "theModel", False)
    result = tested.request()
    expected = HttpResponse(
        code=202,
        response='{"content": [{"text": "```json\\n[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n```\\n"}], '
        '"usage": {"input_tokens": 137, "output_tokens": 43}}',
        tokens=TokenCounts(prompt=0, generated=0),
    )
    assert result == expected

    calls = [call(), call()]
    assert to_dict.mock_calls == calls
    calls = [
        call(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": "apiKey"},
            params={},
            data='{"key": "valueX"}',
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    calls = [
        call.log("--- request begins:"),
        call.log('{\n  "key": "valueY"\n}'),
        call.log("status code: 202"),
        call.log(
            '{"content": [{"text": "```json\\n[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n```\\n"}],'
            ' "usage": {"input_tokens": 137, "output_tokens": 43}}'
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # no error
    response.status_code = 200
    to_dict.side_effect = [{"key": "valueA"}, {"key": "valueB"}]
    requests_post.side_effect = [response]

    tested = LlmAnthropic(memory_log, "apiKey", "theModel", False)
    result = tested.request()
    expected = HttpResponse(
        code=200,
        response='```json\n["line 1","line 2","line 3"]\n```\n',
        tokens=TokenCounts(prompt=137, generated=43),
    )
    assert result == expected

    calls = [call(), call()]
    assert to_dict.mock_calls == calls
    calls = [
        call(
            "https://api.anthropic.com/v1/messages",
            headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01", "x-api-key": "apiKey"},
            params={},
            data='{"key": "valueA"}',
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    calls = [
        call.log("--- request begins:"),
        call.log('{\n  "key": "valueB"\n}'),
        call.log("status code: 200"),
        call.log(
            '{"content": [{"text": "```json\\n[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n```\\n"}],'
            ' "usage": {"input_tokens": 137, "output_tokens": 43}}'
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
