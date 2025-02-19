import json
from unittest.mock import patch, call

from logger import log

from commander.protocols.llms.llm_openai import LlmOpenai
from commander.protocols.structures.http_response import HttpResponse
from commander.protocols.structures.json_extract import JsonExtract


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
    tested.system_prompt = ["line 1", "line 2", "line 3"]
    tested.user_prompt = ["line 4", "line 5", "line 6"]
    #
    result = tested.to_dict()
    expected = {
        'messages': [
            {'content': 'line 1\nline 2\nline 3', 'role': 'system'},
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
            {'content': 'line 1\nline 2\nline 3', 'role': 'system'},
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


@patch("commander.protocols.llms.llm_openai.requests_post")
def test_post(requests_post):
    def reset_mocks():
        requests_post.reset_mock()

    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    tested = LlmOpenai("openaiKey", "theModel")
    result = tested.post("theUrl", {"param": "value"}, "theData", 123)
    expected = HttpResponse(code=202, response="theResponse")
    assert result == expected

    calls = [call(
        "theUrl",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer openaiKey",
            "OpenAI-Beta": "assistants=v2",
        },
        params={"param": "value"},
        data="theData",
        verify=True,
        timeout=123,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()


@patch.object(log, "info")
@patch.object(LlmOpenai, "post")
def test_chat(post, info):
    def reset_mocks():
        post.reset_mock()
        info.reset_mock()

    tested = LlmOpenai("openaiKey", "theModel")
    # all good
    response = {
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
    }
    expected = JsonExtract(error='', has_error=False, content=[['item1', 'item2'], ['item3']])
    calls = [call(
        "https://api.openai.com/v1/chat/completions",
        {},
        '{"model": "theModel", '
        '"modalities": ["text"], '
        '"messages": [{"role": "system", "content": ""}, {"role": "user", "content": [{"type": "text", "text": ""}]}], '
        '"temperature": 0.0}',
    )]
    # -- no log
    post.side_effect = [HttpResponse(code=200, response=json.dumps(response))]
    result = tested.chat()
    assert result == expected
    assert post.mock_calls == calls
    assert info.mock_calls == []
    reset_mocks()
    # -- with log
    post.side_effect = [HttpResponse(code=200, response=json.dumps(response))]
    result = tested.chat(True)
    assert result == expected
    assert post.mock_calls == calls
    info_calls = [
        call('***** CHAT STARTS ******'),
        call('response:\n```json\n["item1", "item2"]\n```\n\n```json\n["item3"]\n```\n\nend.'),
        call('****** CHAT ENDS *******'),
    ]
    assert info.mock_calls == info_calls
    reset_mocks()

    # error
    post.side_effect = [HttpResponse(code=500, response="theResponse")]
    result = tested.chat()
    exp_with_error = JsonExtract("the reported error is: 500", True, [])
    assert result == exp_with_error
    assert post.mock_calls == calls
    info_calls = [
        call('***********'),
        call(500),
        call("theResponse"),
        call('***********'),
    ]
    assert info.mock_calls == info_calls
    reset_mocks()


@patch("commander.protocols.llms.llm_openai.requests_post")
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
