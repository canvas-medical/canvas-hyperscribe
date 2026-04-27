from unittest.mock import patch, call, MagicMock

import pytest
from langdetect.lang_detect_exception import LangDetectException

from hyperscribe.llms.llm_eleven_labs import LlmElevenLabs
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts


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
    expected = HttpResponse(code=422, response="no audio provided", tokens=TokenCounts(prompt=0, generated=0))
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
        tokens=TokenCounts(prompt=0, generated=0),
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
        tokens=TokenCounts(prompt=0, generated=0),
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
        tokens=TokenCounts(prompt=0, generated=0),
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


def test_filter_non_english_turns_empty():
    kept, filtered = LlmElevenLabs._filter_non_english_turns([])
    assert kept == []
    assert filtered == []


def test_filter_non_english_turns_all_english():
    turns = [
        {"speaker_id": "speaker_0", "text": ["Hello", " ", "how", " ", "are", " ", "you"], "start": 0.0, "end": 3.0},
        {"speaker_id": "speaker_1", "text": ["I", " ", "am", " ", "doing", " ", "well"], "start": 3.0, "end": 6.0},
    ]
    kept, filtered = LlmElevenLabs._filter_non_english_turns(turns)
    assert len(kept) == 2
    assert len(filtered) == 0


@patch("hyperscribe.llms.llm_eleven_labs.detect")
def test_filter_non_english_turns_removes_non_english(mock_detect):
    turns = [
        {"speaker_id": "speaker_0", "text": ["Hello", " ", "how", " ", "are", " ", "you"], "start": 0.0, "end": 3.0},
        {
            "speaker_id": "speaker_0",
            "text": ["Zagrożone", " ", "gatunki", " ", "zwierząt"],
            "start": 3.0,
            "end": 6.0,
        },
        {
            "speaker_id": "speaker_1",
            "text": ["I", " ", "feel", " ", "much", " ", "better", " ", "today"],
            "start": 6.0,
            "end": 9.0,
        },
    ]
    mock_detect.side_effect = ["en", "pl", "en"]

    kept, filtered = LlmElevenLabs._filter_non_english_turns(turns)
    assert len(kept) == 2
    assert kept[0]["start"] == 0.0
    assert kept[1]["start"] == 6.0
    assert len(filtered) == 1
    assert filtered[0]["start"] == 3.0


@patch("hyperscribe.llms.llm_eleven_labs.detect")
def test_filter_non_english_turns_keeps_silence(mock_detect):
    turns = [
        {"speaker_id": "speaker_0", "text": [], "start": 0.0, "end": 0.0},
        {"speaker_id": "speaker_0", "text": ["[silence]"], "start": 0.0, "end": 0.0},
        {"speaker_id": "speaker_1", "text": ["Hello", " ", "doctor"], "start": 1.0, "end": 3.0},
    ]
    mock_detect.side_effect = ["en"]

    kept, filtered = LlmElevenLabs._filter_non_english_turns(turns)
    assert len(kept) == 3
    assert len(filtered) == 0
    # detect should only be called once (for the English turn)
    assert mock_detect.call_count == 1


@patch("hyperscribe.llms.llm_eleven_labs.detect")
def test_filter_non_english_turns_detection_failure_keeps_turn(mock_detect):
    turns = [
        {"speaker_id": "speaker_0", "text": ["ok"], "start": 0.0, "end": 0.5},
        {
            "speaker_id": "speaker_1",
            "text": ["The", " ", "patient", " ", "is", " ", "stable"],
            "start": 0.5,
            "end": 3.0,
        },
    ]
    mock_detect.side_effect = [LangDetectException(0, ""), "en"]

    kept, filtered = LlmElevenLabs._filter_non_english_turns(turns)
    assert len(kept) == 2
    assert len(filtered) == 0


@patch("hyperscribe.llms.llm_eleven_labs.detect")
def test_filter_non_english_turns_all_non_english(mock_detect):
    turns = [
        {
            "speaker_id": "speaker_0",
            "text": ["Bonjour", " ", "comment", " ", "allez-vous"],
            "start": 0.0,
            "end": 3.0,
        },
        {"speaker_id": "speaker_1", "text": ["Zagrożone", " ", "gatunki"], "start": 3.0, "end": 5.0},
    ]
    mock_detect.side_effect = ["fr", "pl"]

    kept, filtered = LlmElevenLabs._filter_non_english_turns(turns)
    assert len(kept) == 0
    assert len(filtered) == 2


@patch("hyperscribe.llms.llm_eleven_labs.log")
@patch("hyperscribe.llms.llm_eleven_labs.detect")
@patch("hyperscribe.llms.llm_eleven_labs.requests_post")
def test_request_logs_exception_for_non_english_turns(requests_post, mock_detect, mock_log):
    import json

    content = {
        "words": [
            {"text": "Hello", "start": 0.0, "end": 0.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": "doctor", "start": 0.5, "end": 1.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "Zagrożone", "start": 2.0, "end": 2.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": "gatunki", "start": 2.5, "end": 3.0, "type": "word", "speaker_id": "speaker_0"},
            {"text": "zwierząt", "start": 3.0, "end": 3.5, "type": "word", "speaker_id": "speaker_0"},
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
    # First turn "Hellodoctor" -> en, second turn "Zagrożonegatunkizwierząt" -> pl
    mock_detect.side_effect = ["en", "pl"]

    memory_log = MagicMock()
    tested = LlmElevenLabs(memory_log, "apiKey", "theModel", False)
    tested.add_audio(b"someBytes", "mp3")
    result = tested.request()

    assert result.code == 200
    # The non-English turn should be filtered out
    response_data = json.loads(result.response.replace("```json\n", "").replace("\n```", ""))
    assert len(response_data) == 1
    assert response_data[0]["text"] == "Hellodoctor"

    # Verify log.exception was called for the non-English turn
    mock_log.exception.assert_called_once()
    exception_msg = mock_log.exception.call_args[0][0]
    assert "Non-English transcript content detected" in exception_msg
    assert "speaker_0" in exception_msg
