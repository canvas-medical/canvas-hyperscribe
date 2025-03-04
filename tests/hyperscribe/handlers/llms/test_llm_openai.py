import json
from unittest.mock import patch, call

from logger import log

from hyperscribe.handlers.llms.llm_openai import LlmOpenai
from hyperscribe.handlers.structures.http_response import HttpResponse


def test_add_audio():
    tested = LlmOpenai("openaiKey", "theModel")
    tested.add_audio(b"", "mp3")
    assert tested.audios == []
    tested.add_audio(b"abc", "mp3")
    expected = [{"format": "mp3", "data": "YWJj"}]
    assert tested.audios == expected


def test_to_dict():
    tested = LlmOpenai("openaiKey", "theModel")
    tested.add_audio(b"abc", "mp3")
    tested.add_audio(b"def", "mp3")
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])
    #
    result = tested.to_dict()
    expected = {
        'messages': [
            {
                'role': 'system',
                'content': [{'text': 'line 1\nline 2\nline 3', 'type': 'text'}],
            },
            {
                'content': [
                    {'text': 'line 4\nline 5\nline 6', 'type': 'text'},
                    {'input_audio': {'data': 'YWJj', 'format': 'mp3'}, 'type': 'input_audio'},
                    {'input_audio': {'data': 'ZGVm', 'format': 'mp3'}, 'type': 'input_audio'},
                ],
                'role': 'user',
            },
        ],
        'modalities': ['text'],
        'model': 'theModel',
        'temperature': 0.0,
    }
    assert result == expected
    # for log
    result = tested.to_dict(True)
    expected = {
        'messages': [
            {
                'role': 'system',
                'content': [{'text': 'line 1\nline 2\nline 3', 'type': 'text'}],
            },
            {
                'content': [
                    {'text': 'line 4\nline 5\nline 6', 'type': 'text'},
                    {'input_audio': "some audio", 'type': 'input_audio'},
                    {'input_audio': "some audio", 'type': 'input_audio'},
                ],
                'role': 'user',
            },
        ],
        'modalities': ['text'],
        'model': 'theModel',
        'temperature': 0.0,
    }
    assert result == expected
    # with an exchange with the model
    tested.set_model_prompt(["line 7", "line 8"])
    tested.set_user_prompt(["line 9", "line 10"])
    result = tested.to_dict()
    expected = {
        'messages': [
            {
                'role': 'system',
                'content': [{'text': 'line 1\nline 2\nline 3', 'type': 'text'}],
            },

            {
                'content': [
                    {'text': 'line 4\nline 5\nline 6', 'type': 'text'},
                    {'input_audio': {'data': 'YWJj', 'format': 'mp3'}, 'type': 'input_audio'},
                    {'input_audio': {'data': 'ZGVm', 'format': 'mp3'}, 'type': 'input_audio'},
                ],
                'role': 'user',
            },
            {
                'role': 'assistant',
                'content': [{'text': 'line 7\nline 8', 'type': 'text'}],
            },

            {
                'role': 'user',
                'content': [{'text': 'line 9\nline 10', 'type': 'text'}],
            },
        ],
        'modalities': ['text'],
        'model': 'theModel',
        'temperature': 0.0,
    }
    assert result == expected


@patch("hyperscribe.handlers.llms.llm_openai.requests_post")
@patch.object(log, "info")
def test_request(info, requests_post):
    def reset_mocks():
        info.reset_mock()
        requests_post.reset_mock()

    response = type("Response", (), {
        "status_code": 202,
        "text": json.dumps({
            "choices": [
                {
                    "message": {
                        "content": "\n".join([
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
                        ]),
                    },
                },
            ],
        }),
    })()
    tested = LlmOpenai("openaiKey", "theModel")
    # all good
    response.status_code = 200
    expected = HttpResponse(
        code=200,
        response='response:\n```json\n["item1", "item2"]\n```\n\n```json\n["item3"]\n```\n\nend.',
    )
    calls = [call(
        'https://api.openai.com/v1/chat/completions',
        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer openaiKey', 'OpenAI-Beta': 'assistants=v2'},
        params={},
        data='{"model": "theModel", "modalities": ["text"], "messages": [], "temperature": 0.0}',
        verify=True,
        timeout=None,
    )]
    # -- no log
    requests_post.side_effect = [response]
    result = tested.request()
    assert result == expected
    assert requests_post.mock_calls == calls
    assert info.mock_calls == []
    reset_mocks()
    # -- with log
    requests_post.side_effect = [response]
    result = tested.request(True)
    assert result == expected
    assert requests_post.mock_calls == calls
    info_calls = [
        call('***** CHAT STARTS ******'),
        call('{\n  "model": "theModel",\n  "modalities": [\n    "text"\n  ],\n  "messages": [],\n  "temperature": 0.0\n}'),
        call('response code: >200<'),
        call('{"choices": [{"message": {"content": "response:'
             '\\n```json\\n[\\"item1\\", \\"item2\\"]\\n```\\n'
             '\\n```json\\n[\\"item3\\"]\\n```\\n\\nend."}}]}'),
        call('****** CHAT ENDS *******'),
    ]
    assert info.mock_calls == info_calls
    reset_mocks()

    # error
    response.status_code = 500
    requests_post.side_effect = [response]
    result = tested.request()
    exp_with_error = HttpResponse(
        code=500,
        response='{"choices": [{"message": {"content": "response:\\n```json\\n[\\"item1\\", \\"item2\\"]\\n```\\n\\n```json\\n[\\"item3\\"]\\n```\\n\\nend."}}]}',
    )
    assert result == exp_with_error
    assert requests_post.mock_calls == calls
    assert info.mock_calls == []
    reset_mocks()


@patch("hyperscribe.handlers.llms.llm_openai.requests_post")
def test_audio_to_text(requests_post):
    def reset_mocks():
        requests_post.reset_mock()

    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    tested = LlmOpenai("openaiKey", "theModel")
    result = tested.audio_to_text(b"abc")
    expected = HttpResponse(code=202, response="theResponse")
    assert result == expected
    calls = [
        call(
            'https://api.openai.com/v1/audio/transcriptions',
            headers={'Authorization': 'Bearer openaiKey'},
            params={},
            data={
                'model': 'whisper-1',
                'language': 'en',
                'prompt': 'The conversation is in the medical context.',
                'response_format': 'text',
            },
            files={'file': ('audio.mp3', b'abc', 'application/octet-stream')},
            verify=True,
        )
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()
