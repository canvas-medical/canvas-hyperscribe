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
        response='```json\n[\n {\n  "speaker": "speaker_0",\n  "text": "[silence]"\n }\n]\n```',
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
            {"text": "text A", "type": "word", "speaker_id": "speaker_0"},
            {"text": "text B", "type": "audio_event", "speaker_id": "speaker_0"},
            {"text": "text C", "type": "word", "speaker_id": "speaker_0"},
            {"text": "text D", "type": "word", "speaker_id": "speaker_0"},
            {"text": "text E", "type": "word", "speaker_id": "speaker_1"},
            {"text": "text F", "type": "spacing", "speaker_id": "speaker_1"},
            {"text": "text G", "type": "word", "speaker_id": "speaker_1"},
            {"text": "text H", "type": "word", "speaker_id": "speaker_2"},
            {"text": "text I", "type": "spacing", "speaker_id": "speaker_2"},
            {"text": "text J", "type": "word", "speaker_id": "speaker_1"},
            {"text": "text K", "type": "word", "speaker_id": "speaker_0"},
            {"text": "text L", "type": "word", "speaker_id": "speaker_1"},
            {"text": "text M", "type": "spacing", "speaker_id": "speaker_1"},
            {"text": "text N", "type": "word", "speaker_id": "speaker_1"},
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
        '{\n  "speaker": "speaker_0",\n  "text": "text Atext Ctext D"\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "text E text G"\n },\n '
        '{\n  "speaker": "speaker_2",\n  "text": "text H "\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "text J"\n },\n '
        '{\n  "speaker": "speaker_0",\n  "text": "text K"\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "text L text N"\n }\n'
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
                    {"text": "text A", "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text B", "type": "audio_event", "speaker_id": "speaker_0"},
                    {"text": "text C", "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text D", "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text E", "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text F", "type": "spacing", "speaker_id": "speaker_1"},
                    {"text": "text G", "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text H", "type": "word", "speaker_id": "speaker_2"},
                    {"text": "text I", "type": "spacing", "speaker_id": "speaker_2"},
                    {"text": "text J", "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text K", "type": "word", "speaker_id": "speaker_0"},
                    {"text": "text L", "type": "word", "speaker_id": "speaker_1"},
                    {"text": "text M", "type": "spacing", "speaker_id": "speaker_1"},
                    {"text": "text N", "type": "word", "speaker_id": "speaker_1"},
                ],
            }
        ),
        call.log("--- request ends ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()
