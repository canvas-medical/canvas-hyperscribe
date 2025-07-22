import json
from unittest.mock import patch, call, MagicMock

from hyperscribe.llms.llm_google import LlmGoogle
from hyperscribe.structures.http_response import HttpResponse


def test_add_audio():
    memory_log = MagicMock()
    tested = LlmGoogle(memory_log, "googleKey", "theModel", False)

    result = tested.audios
    assert result == []

    tested.add_audio(b"", "mp3")
    assert tested.audios == []

    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.audios
    expected = [{"format": "audio/mp3", "data": b"the audio1"}, {"format": "audio/wav", "data": b"the audio2"}]
    assert result == expected
    assert memory_log.mock_calls == []


def test_to_dict():
    memory_log = MagicMock()
    tested = LlmGoogle(memory_log, "googleKey", "theModel", False)
    tested.set_system_prompt(["line 1", "line 2", "line 3"])
    tested.set_user_prompt(["line 4", "line 5", "line 6"])

    #
    result = tested.to_dict([])
    expected = {
        "contents": [
            {"role": "user", "parts": [{"text": "line 1\nline 2\nline 3"}, {"text": "line 4\nline 5\nline 6"}]},
        ],
        "generationConfig": {"temperature": 0.0},
    }
    assert result == expected
    assert memory_log.mock_calls == []

    # with audio
    result = tested.to_dict([("audio/mp3", "uriAudio1"), ("audio/wav", "uriAudio2"), ("audio/mp3", "uriAudio3")])
    expected = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "line 1\nline 2\nline 3"},
                    {"text": "line 4\nline 5\nline 6"},
                    {"file_data": {"mime_type": "audio/mp3", "file_uri": "uriAudio1"}},
                    {"file_data": {"mime_type": "audio/wav", "file_uri": "uriAudio2"}},
                    {"file_data": {"mime_type": "audio/mp3", "file_uri": "uriAudio3"}},
                ],
            },
        ],
        "generationConfig": {"temperature": 0.0},
    }
    assert result == expected
    assert memory_log.mock_calls == []

    # with an exchange with the model
    tested.set_model_prompt(["line 7", "line 8"])
    tested.set_user_prompt(["line 9", "line 10"])
    result = tested.to_dict([("audio/mp3", "uriAudio1")])
    expected = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": "line 1\nline 2\nline 3"},
                    {"text": "line 4\nline 5\nline 6"},
                    {"file_data": {"mime_type": "audio/mp3", "file_uri": "uriAudio1"}},
                ],
            },
            {"role": "model", "parts": [{"text": "line 7\nline 8"}]},
            {"role": "user", "parts": [{"text": "line 9\nline 10"}]},
        ],
        "generationConfig": {"temperature": 0.0},
    }
    assert result == expected
    assert memory_log.mock_calls == []


@patch("hyperscribe.llms.llm_google.requests_post")
def test_upload_audio(requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        requests_post.reset_mock()
        memory_log.reset_mock()

    tested = LlmGoogle(memory_log, "googleKey", "theModel", False)

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
            "https://generativelanguage.googleapis.com/upload/v1beta/files?key=googleKey",
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": "10",
                "X-Goog-Upload-Header-Content-Type": "mp3",
                "Content-Type": "application/json",
            },
            data='{"file": {"display_name": "audio03"}}',
            verify=True,
            timeout=None,
        ),
        call(
            "theUploadUri",
            headers={"Content-Length": "10", "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"},
            params={},
            data=b"the audio1",
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    assert memory_log.mock_calls == []
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
            "https://generativelanguage.googleapis.com/upload/v1beta/files?key=googleKey",
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": "10",
                "X-Goog-Upload-Header-Content-Type": "mp3",
                "Content-Type": "application/json",
            },
            data='{"file": {"display_name": "audio03"}}',
            verify=True,
            timeout=None,
        ),
        call(
            "theUploadUri",
            headers={"Content-Length": "10", "X-Goog-Upload-Offset": "0", "X-Goog-Upload-Command": "upload, finalize"},
            params={},
            data=b"the audio1",
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    assert memory_log.mock_calls == []
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
            "https://generativelanguage.googleapis.com/upload/v1beta/files?key=googleKey",
            headers={
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": "10",
                "X-Goog-Upload-Header-Content-Type": "mp3",
                "Content-Type": "application/json",
            },
            data='{"file": {"display_name": "audio03"}}',
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    assert memory_log.mock_calls == []
    reset_mocks()


@patch("hyperscribe.llms.llm_google.requests_post")
@patch.object(LlmGoogle, "to_dict")
@patch.object(LlmGoogle, "upload_audio")
def test_request(upload_audio, to_dict, requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        upload_audio.reset_mock()
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
                    "candidates": [
                        {
                            "content": {
                                "parts": [{"text": "\n".join(["```json", '["line 1","line 2","line 3"]', "```", ""])}],
                            },
                        },
                    ],
                },
            ),
        },
    )()

    # error
    upload_audio.side_effect = ["uri1", "uri2", "uri3"]
    to_dict.side_effect = [{"key": "valueX"}, {"key": "valueY"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle(memory_log, "apiKey", "theModel", False)
    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    tested.add_audio(b"the audio3", "mp3")
    result = tested.request()
    expected = HttpResponse(
        code=202,
        response='{"candidates": [{"content": {"parts": [{"text": "'
        "```json\\n"
        '[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n'
        '```\\n"}]}}]}',
    )
    assert result == expected

    calls = [
        call(b"the audio1", "audio/mp3", "audio00"),
        call(b"the audio2", "audio/wav", "audio01"),
        call(b"the audio3", "audio/mp3", "audio02"),
    ]
    assert upload_audio.mock_calls == calls
    calls = [
        call([("audio/mp3", "uri1"), ("audio/wav", "uri2"), ("audio/mp3", "uri3")]),
        call([("audio/mp3", "uri1"), ("audio/wav", "uri2"), ("audio/mp3", "uri3")]),
    ]
    assert to_dict.mock_calls == calls
    calls = [
        call(
            "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
            headers={"Content-Type": "application/json"},
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
            '{"candidates": [{"content": {"parts": [{"text": "'
            "```json\\n"
            '[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n'
            '```\\n"}]}}]}',
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # no error
    response.status_code = 200
    upload_audio.side_effect = ["uri1", "uri2"]
    to_dict.side_effect = [{"key": "valueX"}, {"key": "valueY"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle(memory_log, "apiKey", "theModel", False)
    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.request()
    expected = HttpResponse(code=200, response='```json\n["line 1","line 2","line 3"]\n```\n')
    assert result == expected

    calls = [call(b"the audio1", "audio/mp3", "audio00"), call(b"the audio2", "audio/wav", "audio01")]
    assert upload_audio.mock_calls == calls
    calls = [call([("audio/mp3", "uri1"), ("audio/wav", "uri2")]), call([("audio/mp3", "uri1"), ("audio/wav", "uri2")])]
    assert to_dict.mock_calls == calls
    calls = [
        call(
            "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
            headers={"Content-Type": "application/json"},
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
        call.log("status code: 200"),
        call.log(
            '{"candidates": [{"content": {"parts": [{"text": '
            '"```json\\n'
            '[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n'
            '```\\n"}]}}]}',
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
    # no audio
    upload_audio.side_effect = []
    to_dict.side_effect = [{"key": "valueX"}, {"key": "valueY"}]
    requests_post.side_effect = [response]

    tested = LlmGoogle(memory_log, "apiKey", "theModel", False)
    result = tested.request()
    expected = HttpResponse(code=200, response='```json\n["line 1","line 2","line 3"]\n```\n')
    assert result == expected

    assert upload_audio.mock_calls == []
    calls = [call([]), call([])]
    assert to_dict.mock_calls == calls
    calls = [
        call(
            "https://generativelanguage.googleapis.com/v1beta/theModel:generateContent?key=apiKey",
            headers={"Content-Type": "application/json"},
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
        call.log("status code: 200"),
        call.log(
            '{"candidates": [{"content": {"parts": [{"text": "'
            "```json\\n"
            '[\\"line 1\\",\\"line 2\\",\\"line 3\\"]\\n'
            '```\\n"}]}}]}',
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
