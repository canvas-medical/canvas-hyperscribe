import json
from unittest.mock import patch, call, MagicMock

from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts


def test_support_speaker_identification():
    memory_log = MagicMock()
    tested = LlmOpenai(memory_log, "openaiKey", "theModel", False)
    result = tested.support_speaker_identification()
    assert result is True


def test_add_audio():
    memory_log = MagicMock()
    tested = LlmOpenai(memory_log, "openaiKey", "theModel", False)
    tested.add_audio(b"", "mp3")
    assert tested.audios == []
    tested.add_audio(b"abc", "mp3")
    expected = [{"format": "mp3", "data": "YWJj"}]
    assert tested.audios == expected
    assert memory_log.mock_calls == []


def test_to_dict():
    memory_log = MagicMock()
    tested = LlmOpenai(memory_log, "openaiKey", "theModel", False)
    tested.add_audio(b"abc", "mp3")
    tested.add_audio(b"def", "mp3")
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])
    #
    result = tested.to_dict(False)
    expected = {
        "messages": [
            {"role": "system", "content": [{"text": "line 1\nline 2\nline 3", "type": "text"}]},
            {
                "content": [
                    {"text": "line 4\nline 5\nline 6", "type": "text"},
                    {"input_audio": {"data": "YWJj", "format": "mp3"}, "type": "input_audio"},
                    {"input_audio": {"data": "ZGVm", "format": "mp3"}, "type": "input_audio"},
                ],
                "role": "user",
            },
        ],
        "modalities": ["text"],
        "model": "theModel",
        "temperature": 0.0,
    }
    assert result == expected
    assert memory_log.mock_calls == []
    # for log
    result = tested.to_dict(True)
    expected = {
        "messages": [
            {"role": "system", "content": [{"text": "line 1\nline 2\nline 3", "type": "text"}]},
            {
                "content": [
                    {"text": "line 4\nline 5\nline 6", "type": "text"},
                    {"input_audio": "some audio", "type": "input_audio"},
                    {"input_audio": "some audio", "type": "input_audio"},
                ],
                "role": "user",
            },
        ],
        "modalities": ["text"],
        "model": "theModel",
        "temperature": 0.0,
    }
    assert result == expected
    assert memory_log.mock_calls == []
    # with an exchange with the model
    tested.set_model_prompt(["line 7", "line 8"])
    tested.set_user_prompt(["line 9", "line 10"])
    result = tested.to_dict(False)
    expected = {
        "messages": [
            {"role": "system", "content": [{"text": "line 1\nline 2\nline 3", "type": "text"}]},
            {
                "content": [
                    {"text": "line 4\nline 5\nline 6", "type": "text"},
                    {"input_audio": {"data": "YWJj", "format": "mp3"}, "type": "input_audio"},
                    {"input_audio": {"data": "ZGVm", "format": "mp3"}, "type": "input_audio"},
                ],
                "role": "user",
            },
            {"role": "assistant", "content": [{"text": "line 7\nline 8", "type": "text"}]},
            {"role": "user", "content": [{"text": "line 9\nline 10", "type": "text"}]},
        ],
        "modalities": ["text"],
        "model": "theModel",
        "temperature": 0.0,
    }
    assert result == expected
    assert memory_log.mock_calls == []


@patch("hyperscribe.llms.llm_openai.requests_post")
def test_request(requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        requests_post.reset_mock()
        memory_log.reset_mock()

    response = type(
        "Response",
        (),
        {
            "status_code": 202,
            "text": json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "\n".join(
                                    [
                                        "response:",
                                        "```json",
                                        json.dumps(["item1", "item2"]),
                                        "```",
                                        "",
                                        "```json",
                                        json.dumps(["item3"]),
                                        "```",
                                        "",
                                        "end.",
                                    ],
                                ),
                            },
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 178,
                        "completion_tokens": 53,
                    },
                },
            ),
        },
    )()
    tested = LlmOpenai(memory_log, "openaiKey", "theModel", False)
    # all good
    response.status_code = 200
    expected = HttpResponse(
        code=200,
        response='response:\n```json\n["item1", "item2"]\n```\n\n```json\n["item3"]\n```\n\nend.',
        tokens=TokenCounts(prompt=178, generated=53),
    )
    calls_request_post = [
        call(
            "https://us.api.openai.com/v1/chat/completions",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer openaiKey",
                "OpenAI-Beta": "assistants=v2",
            },
            params={},
            data='{"model": "theModel", "modalities": ["text"], "messages": [], "temperature": 0.0}',
            verify=True,
            timeout=None,
        ),
    ]
    requests_post.side_effect = [response]
    result = tested.request()
    assert result == expected
    assert requests_post.mock_calls == calls_request_post
    calls = [
        call.log("--- request begins:"),
        call.log(
            "{"
            '\n  "model": "theModel",'
            '\n  "modalities": [\n    "text"\n  ],'
            '\n  "messages": [],'
            '\n  "temperature": 0.0\n}',
        ),
        call.log("status code: 200"),
        call.log(
            '{"choices": [{"message": {"content": "response:\\n'
            "```json\\n"
            '[\\"item1\\", \\"item2\\"]\\n'
            "```\\n\\n"
            "```json\\n"
            '[\\"item3\\"]\\n'
            "```\\n\\n"
            'end."}}], '
            '"usage": {"prompt_tokens": 178, "completion_tokens": 53}}',
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # error
    response.status_code = 500
    requests_post.side_effect = [response]
    result = tested.request()
    exp_with_error = HttpResponse(
        code=500,
        response='{"choices": [{"message": {"content": "response:'
        "\\n```json"
        '\\n[\\"item1\\", \\"item2\\"]\\n```\\n\\n```json\\n[\\"item3\\"]'
        '\\n```\\n\\nend."}}], '
        '"usage": {"prompt_tokens": 178, "completion_tokens": 53}}',
        tokens=TokenCounts(prompt=0, generated=0),
    )
    assert result == exp_with_error
    assert requests_post.mock_calls == calls_request_post
    calls = [
        call.log("--- request begins:"),
        call.log(
            "{"
            '\n  "model": "theModel",'
            '\n  "modalities": [\n    "text"\n  ],'
            '\n  "messages": [],'
            '\n  "temperature": 0.0\n}',
        ),
        call.log("status code: 500"),
        call.log(
            '{"choices": [{"message": {"content": "response:\\n'
            "```json\\n"
            '[\\"item1\\", \\"item2\\"]\\n'
            "```\\n\\n"
            "```json\\n"
            '[\\"item3\\"]\\n'
            "```\\n\\n"
            'end."}}], '
            '"usage": {"prompt_tokens": 178, "completion_tokens": 53}}',
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.llms.llm_openai.requests_post")
def test_audio_to_text(requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        requests_post.reset_mock()
        memory_log.reset_mock()

    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    tested = LlmOpenai(memory_log, "openaiKey", "theModel", False)
    result = tested.audio_to_text(b"abc")
    expected = HttpResponse(code=202, response="theResponse", tokens=TokenCounts(prompt=0, generated=0))
    assert result == expected
    calls = [
        call(
            "https://us.api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": "Bearer openaiKey"},
            params={},
            data={
                "model": "whisper-1",
                "language": "en",
                "prompt": "The conversation is in the medical context.",
                "response_format": "text",
            },
            files={"file": ("audio.mp3", b"abc", "application/octet-stream")},
            verify=True,
        ),
    ]
    assert requests_post.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()
