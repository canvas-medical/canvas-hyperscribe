import json
from unittest.mock import patch, call

from logger import log

from commander.protocols.llms.llm_google import LlmGoogle
from commander.protocols.structures.json_extract import JsonExtract


def test_add_audio():
    tested = LlmGoogle("googleKey", "theModel")

    result = tested.audios
    assert result == []

    tested.add_audio(b"", "mp3")
    assert tested.audios == []

    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.audios
    expected = [
        {"format": "audio/mp3", "data": b"the audio1", },
        {"format": "audio/wav", "data": b"the audio2", },
    ]
    assert result == expected


def test_to_dict():
    tested = LlmGoogle("googleKey", "theModel")
    tested.system_prompt = ["line 1", "line 2", "line 3"]
    tested.user_prompt = ["line 4", "line 5", "line 6"]

    #
    result = tested.to_dict({})
    expected = {
        'contents': [
            {
                "role": "user",
                "parts": [
                    {"text": "line 1\nline 2\nline 3"},
                    {"text": "line 4\nline 5\nline 6"},
                ],
            },
        ],
        "generationConfig": {'temperature': 0.0},
    }
    assert result == expected

    # with audio
    result = tested.to_dict({"audio/mp3": "uriAudio1", "audio/wav": "uriAudio2"})
    expected = {
        'contents': [
            {
                "role": "user",
                "parts": [
                    {"text": "line 1\nline 2\nline 3"},
                    {"text": "line 4\nline 5\nline 6"},
                    {"file_data": {"mime_type": "audio/mp3", "file_uri": "uriAudio1"}},
                    {"file_data": {"mime_type": "audio/wav", "file_uri": "uriAudio2"}},
                ],
            },
        ],
        "generationConfig": {'temperature': 0.0},
    }
    assert result == expected


@patch("commander.protocols.llms.llm_google.requests_post")
def test_upload_audio(requests_post):
    def reset_mocks():
        requests_post.reset_mock()

    tested = LlmGoogle("googleKey", "theModel")

    # all good
    requests_post.side_effect = [
        type("Response", (), {"status_code": 200, "headers": {"x-goog-upload-url": "theUploadUri"}})(),
        type("Response", (), {"status_code": 200, "text": json.dumps({"file": {"uri": "theFileUri"}})}),
    ]
    result = tested.upload_audio(b"the audio1", "mp3", "audio03")
    expected = "theFileUri"
    assert result == expected
    calls = [
        call(
            'https://generativelanguage.googleapis.com/upload/v1beta/files?key=googleKey',
            headers={
                'X-Goog-Upload-Protocol': 'resumable',
                'X-Goog-Upload-Command': 'start',
                'X-Goog-Upload-Header-Content-Length': '10',
                'X-Goog-Upload-Header-Content-Type': 'mp3',
                'Content-Type': 'application/json',
            },
            data='{"file": {"display_name": "audio03"}}',
            verify=True,
            timeout=None,
        ),
        call(
            'theUploadUri',
            headers={
                'Content-Length': '10',
                'X-Goog-Upload-Offset': '0',
                'X-Goog-Upload-Command': 'upload, finalize',
            },
            params={},
            data=b'the audio1',
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()

    # upload fails
    requests_post.side_effect = [
        type("Response", (), {"status_code": 200, "headers": {"x-goog-upload-url": "theUploadUri"}})(),
        type("Response", (), {"status_code": 500, "text": json.dumps({"file": {"uri": "theFileUri"}})}),
    ]
    result = tested.upload_audio(b"the audio1", "mp3", "audio03")
    expected = ""
    assert result == expected
    calls = [
        call(
            'https://generativelanguage.googleapis.com/upload/v1beta/files?key=googleKey',
            headers={
                'X-Goog-Upload-Protocol': 'resumable',
                'X-Goog-Upload-Command': 'start',
                'X-Goog-Upload-Header-Content-Length': '10',
                'X-Goog-Upload-Header-Content-Type': 'mp3',
                'Content-Type': 'application/json',
            },
            data='{"file": {"display_name": "audio03"}}',
            verify=True,
            timeout=None,
        ),
        call(
            'theUploadUri',
            headers={
                'Content-Length': '10',
                'X-Goog-Upload-Offset': '0',
                'X-Goog-Upload-Command': 'upload, finalize',
            },
            params={},
            data=b'the audio1',
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()

    # initial call fails
    requests_post.side_effect = [
        type("Response", (), {"status_code": 500, "headers": {"x-goog-upload-url": "theUploadUri"}})(),
    ]
    result = tested.upload_audio(b"the audio1", "mp3", "audio03")
    expected = ""
    assert result == expected
    calls = [
        call(
            'https://generativelanguage.googleapis.com/upload/v1beta/files?key=googleKey',
            headers={
                'X-Goog-Upload-Protocol': 'resumable',
                'X-Goog-Upload-Command': 'start',
                'X-Goog-Upload-Header-Content-Length': '10',
                'X-Goog-Upload-Header-Content-Type': 'mp3',
                'Content-Type': 'application/json',
            },
            data='{"file": {"display_name": "audio03"}}',
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    reset_mocks()


@patch("commander.protocols.llms.llm_google.requests_post")
@patch.object(log, "info")
@patch.object(LlmGoogle, "to_dict")
@patch.object(LlmGoogle, "upload_audio")
def test_chat(upload_audio, to_dict, info, requests_post):
    def reset_mocks():
        upload_audio.reset_mock()
        to_dict.reset_mock()
        info.reset_mock()
        requests_post.reset_mock()

    response = type("Response", (), {
        "status_code": 202,
        "text": json.dumps({
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "\n".join([
                                '```json',
                                '["line 1","line 2","line 3"]',
                                '```',
                                '',
                            ])},
                        ],
                    },
                },
            ],
        }),
    })()

    # error
    upload_audio.side_effect = ["uri1", "uri2"]
    to_dict.side_effect = [{"key": "value"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle("apiKey", "theModel")
    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.chat()
    expected = JsonExtract("the reported error is: 202", True, [])
    assert result == expected

    calls = [
        call(b'the audio1', 'audio/mp3', 'audio00'),
        call(b'the audio2', 'audio/wav', 'audio01'),
    ]
    assert upload_audio.mock_calls == calls
    calls = [call({'audio/mp3': 'uri1', 'audio/wav': 'uri2'})]
    assert to_dict.mock_calls == calls
    calls = [
        call("***********"),
        call(202),
        call('{"candidates": [{"content": {"parts": [{"text": "```json\\n[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n```\\n"}]}}]}'),
        call("***********"),
    ]
    assert info.mock_calls == calls
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
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
    upload_audio.side_effect = ["uri1", "uri2"]
    to_dict.side_effect = [{"key": "value"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle("apiKey", "theModel")
    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.chat(True)
    expected = JsonExtract("", False, ["line 1", "line 2", "line 3"])
    assert result == expected

    calls = [
        call(b'the audio1', 'audio/mp3', 'audio00'),
        call(b'the audio2', 'audio/wav', 'audio01'),
    ]
    assert upload_audio.mock_calls == calls
    calls = [call({'audio/mp3': 'uri1', 'audio/wav': 'uri2'})]
    assert to_dict.mock_calls == calls
    calls = [
        call("***** CHAT STARTS ******"),
        call('```json\n["line 1","line 2","line 3"]\n```\n'),
        call("****** CHAT ENDS *******"),
    ]
    assert info.mock_calls == calls
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
    # -- without log
    upload_audio.side_effect = ["uri1", "uri2"]
    to_dict.side_effect = [{"key": "value"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle("apiKey", "theModel")
    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.chat()
    expected = JsonExtract("", False, ["line 1", "line 2", "line 3"])
    assert result == expected

    calls = [
        call(b'the audio1', 'audio/mp3', 'audio00'),
        call(b'the audio2', 'audio/wav', 'audio01'),
    ]
    assert upload_audio.mock_calls == calls
    calls = [call({'audio/mp3': 'uri1', 'audio/wav': 'uri2'})]
    assert to_dict.mock_calls == calls
    assert info.mock_calls == []
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
    # -- without log + no audio
    upload_audio.side_effect = []
    to_dict.side_effect = [{"key": "value"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle("apiKey", "theModel")
    result = tested.chat()
    expected = JsonExtract("", False, ["line 1", "line 2", "line 3"])
    assert result == expected

    assert upload_audio.mock_calls == []
    calls = [call({})]
    assert to_dict.mock_calls == calls
    assert info.mock_calls == []
    calls = [call(
        "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
        headers={"Content-Type": "application/json"},
        params={},
        data='{"key": "value"}',
        verify=True,
        timeout=None,
    )]
    assert requests_post.mock_calls == calls
    reset_mocks()
