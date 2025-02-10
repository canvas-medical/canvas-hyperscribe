import json
from unittest.mock import patch, MagicMock, call

from logger import log

from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.http_response import HttpResponse
from commander.protocols.structures.json_extract import JsonExtract


def test___init__():
    tested = OpenaiChat("openaiKey", "theModel")
    assert tested.openai_key == "openaiKey"
    assert tested.model == "theModel"
    assert tested.temperature == 0.0
    assert tested.system_prompt == []
    assert tested.user_prompt == []
    assert tested.audios == []


def test_add_audio():
    tested = OpenaiChat("openaiKey", "theModel")
    tested.add_audio(b"", "mp3")
    assert tested.audios == []
    tested.add_audio(b"abc", "mp3")
    expected = [{"format": "mp3", "data": "YWJj"}]
    assert tested.audios == expected


def test_to_dict():
    tested = OpenaiChat("openaiKey", "theModel")
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


@patch("commander.protocols.openai_chat.requests_post")
def test_post(requests_post):
    def reset_mocks():
        requests_post.reset_mock()

    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    tested = OpenaiChat("openaiKey", "theModel")
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
@patch.object(OpenaiChat, "post")
def test_chat(post, info):
    def reset_mocks():
        post.reset_mock()
        info.reset_mock()

    tested = OpenaiChat("openaiKey", "theModel")
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


def test_chat_instance():
    tested = OpenaiChat
    result = tested.chat_instance("openaiKey")
    assert isinstance(result, OpenaiChat)
    assert result.openai_key == "openaiKey"
    assert result.model == "gpt-4o"


@patch.object(OpenaiChat, "chat_instance")
def test_single_conversation(chat_instance):
    mock = MagicMock()

    system_prompt = ["theSystemPrompt"]
    user_prompt = ["theUserPrompt"]
    tested = OpenaiChat

    def reset_mocks():
        chat_instance.reset_mock()
        mock.reset_mock()

    # without error
    chat_instance.side_effect = [mock]
    mock.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=["theContent"])]
    result = tested.single_conversation("openaiKey", system_prompt, user_prompt)
    assert result == ["theContent"]

    calls = [call("openaiKey")]
    assert chat_instance.mock_calls == calls
    assert mock.system_prompt == system_prompt
    assert mock.user_prompt == user_prompt
    calls = [call.chat()]
    assert mock.mock_calls == calls
    reset_mocks()

    # with error
    chat_instance.side_effect = [mock]
    mock.chat.side_effect = [JsonExtract(error="theError", has_error=True, content=["theContent"])]
    result = tested.single_conversation("openaiKey", system_prompt, user_prompt)
    assert result == []

    calls = [call("openaiKey")]
    assert chat_instance.mock_calls == calls
    assert mock.system_prompt == system_prompt
    assert mock.user_prompt == user_prompt
    calls = [call.chat()]
    assert mock.mock_calls == calls
    reset_mocks()


@patch.object(log, "info")
def test_extract_json_from(info):
    def reset_mocks():
        info.reset_mock()

    tested = OpenaiChat
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


@patch("commander.protocols.openai_chat.requests_post")
def test_audio_to_text(requests_post):
    def reset_mocks():
        requests_post.reset_mock()

    requests_post.return_value.status_code = 202
    requests_post.return_value.text = "theResponse"

    tested = OpenaiChat("openaiKey", "theModel")
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
