from unittest.mock import patch, call, MagicMock

from hyperscribe.llms.llm_eleven_labs import LlmElevenLabs
from hyperscribe.structures.http_response import HttpResponse


def test_support_speaker_identification():
    memory_log = MagicMock()
    tested = LlmElevenLabs(memory_log, "elevenLabsKey", "theModel", False)
    result = tested.support_speaker_identification()
    assert result is False


def test_add_audio():
    memory_log = MagicMock()
    tested = LlmElevenLabs(memory_log, "elevenLabsKey", "theModel", False)

    result = tested.audios
    assert result == []

    tested.add_audio(b"", "mp3")
    assert tested.audios == []

    tested.add_audio(b"the audio1", "mp3")
    tested.add_audio(b"the audio2", "wav")
    result = tested.audios
    expected = [{"data": b"the audio1"}, {"data": b"the audio2"}]
    assert result == expected
    assert memory_log.mock_calls == []


@patch("hyperscribe.llms.llm_eleven_labs.requests_post")
def test_request(requests_post):
    memory_log = MagicMock()

    def reset_mocks():
        requests_post.reset_mock()
        memory_log.reset_mock()

    # no audio
    requests_post.side_effect = []

    tested = LlmElevenLabs(memory_log, "apiKey", "theModel", False)
    result = tested.request()
    expected = HttpResponse(code=422, response="no audio provided")
    assert result == expected

    assert requests_post.mock_calls == []
    reset_mocks()

    # error
    content = {"error": "theError"}
    import json

    response = type(
        "Response",
        (),
        {
            "status_code": 202,
            "text": json.dumps(content),
            "json": lambda self: content,
        },
    )()
    requests_post.side_effect = [response]

    tested = LlmElevenLabs(memory_log, "apiKey", "theModel", False)
    tested.add_audio(b"someBytes", "mp3")
    result = tested.request()
    expected = HttpResponse(
        code=202,
        response='{"error": "theError"}',
    )
    assert result == expected

    calls = [
        call(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": "apiKey"},
            params={},
            data={"model_id": "theModel", "diarize": True, "temperature": 0},
            files={"file": b"someBytes"},
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    calls = [
        call.log("--- request begins:"),
        call.log("status code: 202"),
        call.log({"error": "theError"}),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    # no error
    #  -- empty response
    content = {
        "words": [],
    }
    response = type(
        "Response",
        (),
        {
            "status_code": 200,
            "text": json.dumps(content),
            "json": lambda self: content,
        },
    )()

    requests_post.side_effect = [response]

    tested = LlmElevenLabs(memory_log, "apiKey", "theModel", False)
    tested.add_audio(b"someBytes", "mp3")
    result = tested.request()
    expected = HttpResponse(
        code=200,
        response="```json\n[\n {"
        '\n  "speaker": "speaker_0",'
        '\n  "text": "[silence]",'
        '\n  "start": 0.0,'
        '\n  "end": 0.0'
        "\n }\n]\n```",
    )
    assert result == expected

    calls = [
        call(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": "apiKey"},
            params={},
            data={"model_id": "theModel", "diarize": True, "temperature": 0},
            files={"file": b"someBytes"},
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    calls = [
        call.log("--- request begins:"),
        call.log("status code: 200"),
        call.log({"words": []}),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    #  -- not empty response
    content = {
        "words": [
            {"text": "text A", "start": 0.0, "end": 1.3, "type": "word", "speaker_id": "speaker_0"},
            {"text": "text B", "start": 1.3, "end": 2.5, "type": "audio_event", "speaker_id": "speaker_0"},
            {"text": "text C", "start": 2.5, "end": 3.6, "type": "word", "speaker_id": "speaker_0"},
            {"text": "text D", "start": 3.6, "end": 4.7, "type": "word", "speaker_id": "speaker_0"},
            {"text": "text E", "start": 4.7, "end": 5.3, "type": "word", "speaker_id": "speaker_1"},
            {"text": "text F", "start": 5.3, "end": 6.4, "type": "spacing", "speaker_id": "speaker_1"},
            {"text": "text G", "start": 6.4, "end": 7.1, "type": "word", "speaker_id": "speaker_1"},
            {"text": "text H", "start": 7.1, "end": 8.0, "type": "word", "speaker_id": "speaker_2"},
            {"text": "text I", "start": 8.0, "end": 9.9, "type": "spacing", "speaker_id": "speaker_2"},
            {"text": "text J", "start": 9.9, "end": 11.3, "type": "word", "speaker_id": "speaker_1"},
            {"text": "text K", "start": 11.3, "end": 12.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": "text L", "start": 12.5, "end": 13.6, "type": "word", "speaker_id": "speaker_1"},
            {"text": "text M", "start": 13.6, "end": 14.7, "type": "spacing", "speaker_id": "speaker_1"},
            {"text": "text N", "start": 14.7, "end": 15.3, "type": "word", "speaker_id": "speaker_1"},
        ],
    }
    response = type(
        "Response",
        (),
        {
            "status_code": 200,
            "text": json.dumps(content),
            "json": lambda self: content,
        },
    )()

    requests_post.side_effect = [response]

    tested = LlmElevenLabs(memory_log, "apiKey", "theModel", False)
    tested.add_audio(b"someBytes", "mp3")
    result = tested.request()
    expected = HttpResponse(
        code=200,
        response="```json\n"
        "[\n "
        '{\n  "speaker": "speaker_0",\n  "text": "text Atext Ctext D",\n  "start": 0.0,\n  "end": 4.7\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "text E text G",\n  "start": 4.7,\n  "end": 7.1\n },\n '
        '{\n  "speaker": "speaker_2",\n  "text": "text H ",\n  "start": 7.1,\n  "end": 9.9\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "text J",\n  "start": 9.9,\n  "end": 11.3\n },\n '
        '{\n  "speaker": "speaker_0",\n  "text": "text K",\n  "start": 11.3,\n  "end": 12.5\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "text L text N",\n  "start": 12.5,\n  "end": 15.3\n }\n'
        "]\n"
        "```",
    )
    assert result == expected

    calls = [
        call(
            "https://api.elevenlabs.io/v1/speech-to-text",
            headers={"xi-api-key": "apiKey"},
            params={},
            data={"model_id": "theModel", "diarize": True, "temperature": 0},
            files={"file": b"someBytes"},
            verify=True,
            timeout=None,
        ),
    ]
    assert requests_post.mock_calls == calls
    calls = [
        call.log("--- request begins:"),
        call.log("status code: 200"),
        call.log(
            {
                "words": [
                    {"text": "text A", "start": 0.0, "end": 1.3, "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text B", "start": 1.3, "end": 2.5, "type": "audio_event", "speaker_id": "speaker_0"},
                    {"text": "text C", "start": 2.5, "end": 3.6, "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text D", "start": 3.6, "end": 4.7, "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text E", "start": 4.7, "end": 5.3, "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text F", "start": 5.3, "end": 6.4, "type": "spacing", "speaker_id": "speaker_1"},
                    {"text": "text G", "start": 6.4, "end": 7.1, "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text H", "start": 7.1, "end": 8.0, "type": "word", "speaker_id": "speaker_2"},
                    {"text": "text I", "start": 8.0, "end": 9.9, "type": "spacing", "speaker_id": "speaker_2"},
                    {"text": "text J", "start": 9.9, "end": 11.3, "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text K", "start": 11.3, "end": 12.5, "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text L", "start": 12.5, "end": 13.6, "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text M", "start": 13.6, "end": 14.7, "type": "spacing", "speaker_id": "speaker_1"},
                    {"text": "text N", "start": 14.7, "end": 15.3, "type": "word", "speaker_id": "speaker_1"},
                ],
            }
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
