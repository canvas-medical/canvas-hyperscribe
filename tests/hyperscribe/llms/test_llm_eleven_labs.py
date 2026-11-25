from unittest.mock import patch, call, MagicMock

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
    assert tested.audio_quality_warnings == []

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

    #  -- hallucinated words are filtered out
    content = {
        "words": [
            {"text": "Take", "start": 0.0, "end": 0.3, "type": "word", "speaker_id": "speaker_0"},
            {"text": " ", "start": 0.3, "end": 0.4, "type": "spacing", "speaker_id": "speaker_0"},
            {"text": "it", "start": 0.4, "end": 0.7, "type": "word", "speaker_id": "speaker_0"},
            {"text": " ", "start": 0.7, "end": 0.8, "type": "spacing", "speaker_id": "speaker_1"},
            {"text": "ok", "start": 0.8, "end": 0.8, "type": "word", "speaker_id": "speaker_1"},
            {"text": " ", "start": 0.8, "end": 0.9, "type": "spacing", "speaker_id": "speaker_1"},
            {"text": "daily", "start": 0.9, "end": 1.2, "type": "word", "speaker_id": "speaker_0"},
            {"text": "quit", "start": 1.2, "end": 1.4, "type": "word", "speaker_id": "speaker_0"},
            {"text": "smoking", "start": 1.2, "end": 1.5, "type": "word", "speaker_id": "speaker_0"},
            {"text": "now", "start": 1.2, "end": 1.6, "type": "word", "speaker_id": "speaker_0"},
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
        '{\n  "speaker": "speaker_0",\n  "text": "Take it",\n  "start": 0.0,\n  "end": 0.7\n },\n '
        '{\n  "speaker": "speaker_1",\n  "text": "[silence]",\n  "start": 0.7,\n  "end": 0.9\n },\n '
        '{\n  "speaker": "speaker_0",\n  "text": "daily",\n  "start": 0.9,\n  "end": 1.2\n }\n'
        "]\n"
        "```",
        tokens=TokenCounts(prompt=0, generated=0),
    )
    assert result == expected
    assert tested.audio_quality_warnings == []

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
        call.log(content),
        call.log("--- request ends ---"),
        call.log("--- filtered 4 hallucinated word(s) ---"),
    ]
    assert memory_log.mock_calls == calls
    reset_mocks()

    #  -- a long silence is reported whatever turn its spacing joins, even inside one turn or split by a filtered word
    one_gap = [
        "Audio quality issue detected: 1 gap(s) longer than 10s found in transcript. Some segments may be unreliable."
    ]
    tests = [
        (
            [
                {"text": "Hello", "start": 0.0, "end": 5.0, "type": "word", "speaker_id": "speaker_0"},
                {"text": " ", "start": 5.0, "end": 50.0, "type": "spacing", "speaker_id": "speaker_0"},
                {"text": "Hi", "start": 50.0, "end": 52.0, "type": "word", "speaker_id": "speaker_1"},
            ],
            '{\n  "speaker": "speaker_0",\n  "text": "Hello ",\n  "start": 0.0,\n  "end": 50.0\n },\n '
            '{\n  "speaker": "speaker_1",\n  "text": "Hi",\n  "start": 50.0,\n  "end": 52.0\n }\n',
            [],
        ),
        (
            [
                {"text": "Hello", "start": 0.0, "end": 5.0, "type": "word", "speaker_id": "speaker_0"},
                {"text": " ", "start": 5.0, "end": 50.0, "type": "spacing", "speaker_id": "speaker_1"},
                {"text": "Hi", "start": 50.0, "end": 52.0, "type": "word", "speaker_id": "speaker_1"},
            ],
            '{\n  "speaker": "speaker_0",\n  "text": "Hello",\n  "start": 0.0,\n  "end": 5.0\n },\n '
            '{\n  "speaker": "speaker_1",\n  "text": " Hi",\n  "start": 5.0,\n  "end": 52.0\n }\n',
            [],
        ),
        (
            [
                {"text": "Hello", "start": 0.0, "end": 5.0, "type": "word", "speaker_id": "speaker_0"},
                {"text": " ", "start": 5.0, "end": 27.0, "type": "spacing", "speaker_id": "speaker_0"},
                {"text": "ok", "start": 27.0, "end": 27.0, "type": "word", "speaker_id": "speaker_0"},
                {"text": " ", "start": 27.0, "end": 50.0, "type": "spacing", "speaker_id": "speaker_0"},
                {"text": "Hi", "start": 50.0, "end": 52.0, "type": "word", "speaker_id": "speaker_0"},
            ],
            '{\n  "speaker": "speaker_0",\n  "text": "Hello  Hi",\n  "start": 0.0,\n  "end": 52.0\n }\n',
            [call.log("--- filtered 1 hallucinated word(s) ---")],
        ),
    ]
    for idx, (words, expected_turns, exp_filter_calls) in enumerate(tests):
        content = {"words": words}
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
            response="```json\n[\n " + expected_turns + "]\n```",
            tokens=TokenCounts(prompt=0, generated=0),
        )
        assert result == expected, f"---> {idx}"
        assert tested.audio_quality_warnings == one_gap, f"---> {idx}"

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
        assert requests_post.mock_calls == calls, f"---> {idx}"
        calls = [
            call.log("--- request begins:"),
            call.log("status code: 200"),
            call.log(content),
            call.log("--- request ends ---"),
        ] + exp_filter_calls
        assert memory_log.mock_calls == calls, f"---> {idx}"
        reset_mocks()


def test__filter_hallucinated_words():
    tested = LlmElevenLabs

    def entry(text: str, start: float, end: float, entry_type: str = "word") -> dict:
        return {"text": text, "start": start, "end": end, "type": entry_type, "speaker_id": "speaker_0"}

    tests = [
        # no words
        ([], [], 0),
        # no hallucination, two words sharing a start are kept
        (
            [entry("A", 0.0, 0.4), entry(" ", 0.4, 0.5, "spacing"), entry("B", 0.5, 0.8), entry("C", 0.5, 0.9)],
            [entry("A", 0.0, 0.4), entry(" ", 0.4, 0.5, "spacing"), entry("B", 0.5, 0.8), entry("C", 0.5, 0.9)],
            0,
        ),
        # zero-duration word
        (
            [entry("A", 0.0, 0.4), entry("B", 0.4, 0.4), entry("C", 0.5, 0.9)],
            [entry("A", 0.0, 0.4), entry("C", 0.5, 0.9)],
            1,
        ),
        # three words sharing a start
        (
            [
                entry("A", 0.0, 0.4),
                entry("B", 0.5, 0.8),
                entry("C", 0.5, 0.9),
                entry("D", 0.5, 1.0),
                entry("E", 1.0, 1.3),
            ],
            [entry("A", 0.0, 0.4), entry("E", 1.0, 1.3)],
            3,
        ),
        # spacing and audio events are kept, whatever their timestamps
        (
            [
                entry("B", 0.5, 0.8),
                entry(" ", 0.5, 0.5, "spacing"),
                entry("C", 0.5, 0.9),
                entry("(cough)", 0.5, 0.5, "audio_event"),
                entry("D", 0.5, 1.0),
            ],
            [entry(" ", 0.5, 0.5, "spacing"), entry("(cough)", 0.5, 0.5, "audio_event")],
            3,
        ),
    ]
    for idx, (words, expected, expected_removed) in enumerate(tests):
        result = tested._filter_hallucinated_words(words)
        assert result == (expected, expected_removed), f"---> {idx}"


def test__detect_audio_quality_issues():
    tested = LlmElevenLabs

    def entry(text: str, start: float, end: float, entry_type: str = "word") -> dict:
        return {"text": text, "start": start, "end": end, "type": entry_type, "speaker_id": "speaker_0"}

    one_gap = [
        "Audio quality issue detected: 1 gap(s) longer than 10s found in transcript. Some segments may be unreliable."
    ]
    two_gaps = [
        "Audio quality issue detected: 2 gap(s) longer than 10s found in transcript. Some segments may be unreliable."
    ]
    tests = [
        # no word or a single word
        ([], []),
        ([entry("A", 0.0, 0.5)], []),
        # silence of exactly 10s
        ([entry("A", 0.0, 0.5), entry(" ", 0.5, 10.5, "spacing"), entry("B", 10.5, 11.0)], []),
        # one silence, covered by a spacing or not
        ([entry("A", 0.0, 0.5), entry(" ", 0.5, 11.0, "spacing"), entry("B", 11.0, 11.5)], one_gap),
        ([entry("A", 0.0, 0.5), entry("B", 11.0, 11.5)], one_gap),
        # an audio event does not end a silence
        ([entry("A", 0.0, 0.5), entry("(cough)", 5.0, 5.5, "audio_event"), entry("B", 11.0, 11.5)], one_gap),
        # two silences
        ([entry("A", 0.0, 0.5), entry("B", 11.0, 11.5), entry("C", 22.0, 22.5)], two_gaps),
    ]
    for idx, (words, expected) in enumerate(tests):
        result = tested._detect_audio_quality_issues(words)
        assert result == expected, f"---> {idx}"
