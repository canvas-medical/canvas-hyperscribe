from datetime import datetime, date
from enum import Enum
from unittest.mock import patch, call, MagicMock

import pytest

from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.llms.llm_eleven_labs import LlmElevenLabs
from hyperscribe.llms.llm_google import LlmGoogle
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


@patch("hyperscribe.libraries.helper.thread_cleanup")
def test_with_cleanup(thread_cleanup):
    function = MagicMock()

    def reset_mocks():
        thread_cleanup.reset_mock()
        function.reset_mock()

    tested = Helper

    # no error
    function.side_effect = ["theResult"]
    result = tested.with_cleanup(function)("a", "b", c="c")
    assert result == "theResult"
    calls = [call("a", "b", c="c")]
    assert function.mock_calls == calls
    calls = [call()]
    assert thread_cleanup.mock_calls == calls
    reset_mocks()

    # with error
    with pytest.raises(ValueError, match="Test error"):
        function.side_effect = [ValueError("Test error")]
        result = tested.with_cleanup(function)("x", "y", z="z")
    calls = [call("x", "y", z="z")]
    assert function.mock_calls == calls
    calls = [call()]
    assert thread_cleanup.mock_calls == calls
    reset_mocks()


def test_str2datetime():
    tested = Helper
    tests = [
        (None, None),
        ("2025-02-04", datetime(2025, 2, 4)),
        ("2025-02", None),
        ("02-04-2025", None),
        ("20250204", None),
    ]
    for string, expected in tests:
        result = tested.str2datetime(string)
        assert result == expected, f"---> {string}"


@patch.object(Helper, "str2datetime")
def test_str2date(str2datetime):
    def reset_mocks():
        str2datetime.reset_mock()

    tested = Helper
    tests = [(None, None), (datetime(2025, 2, 4), date(2025, 2, 4))]
    for side_effect, expected in tests:
        str2datetime.side_effect = [side_effect]
        result = tested.str2date("any")
        assert result == expected, f"---> {side_effect}"
        calls = [call("any")]
        assert str2datetime.mock_calls == calls
        reset_mocks()


def test_enum_or_none():
    class Something(Enum):
        OPTION_1 = 1
        OPTION_2 = 2
        OPTION_A = "A"
        OPTION_B = "B"

    tests = [
        (1, Something.OPTION_1),
        (2, Something.OPTION_2),
        (3, None),
        ("1", None),
        ("A", Something.OPTION_A),
        ("B", Something.OPTION_B),
        ("C", None),
    ]
    tested = Helper
    for value, expected in tests:
        result = tested.enum_or_none(value, Something)
        assert result == expected, f"---> {value}"


def test_icd10_add_dot():
    tested = Helper
    tests = [("I1234", "I12.34"), ("I12", "I12"), ("I1", "I1"), ("I123", "I12.3")]
    for code, expected in tests:
        result = tested.icd10_add_dot(code)
        assert result == expected, f"---> {code}"


def test_icd10_strip_dot():
    tested = Helper
    tests = [("I12.34", "I1234"), ("I12", "I12"), ("I123", "I123")]
    for code, expected in tests:
        result = tested.icd10_strip_dot(code)
        assert result == expected, f"---> {code}"


def test_chatter():
    memory_log = MagicMock()
    tested = Helper
    tests = [
        ("Anthropic", LlmAnthropic, "claude-3-5-sonnet-20241022"),
        ("Google", LlmGoogle, "models/gemini-2.0-flash"),
        ("Any", LlmOpenai, "gpt-4o"),
    ]
    for vendor, exp_class, exp_model in tests:
        memory_log.reset_mock()
        result = tested.chatter(
            Settings(
                llm_text=VendorKey(vendor=vendor, api_key="textKey"),
                llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
                structured_rfv=False,
                audit_llm=False,
                is_tuning=False,
                api_signing_key="theApiSigningKey",
                max_workers=3,
                send_progress=False,
                commands_policy=AccessPolicy(policy=False, items=[]),
                staffers_policy=AccessPolicy(policy=False, items=[]),
                cycle_transcript_overlap=37,
            ),
            memory_log,
        )
        assert memory_log.mock_calls == []
        assert isinstance(result, exp_class)
        assert result.api_key == "textKey"
        assert result.model == exp_model
        assert result.memory_log == memory_log


def test_audio2texter():
    memory_log = MagicMock()
    tested = Helper
    tests = [
        ("Google", LlmGoogle, "models/gemini-2.0-flash"),
        ("ElevenLabs", LlmElevenLabs, "scribe_v1"),
        ("Any", LlmOpenai, "gpt-4o-audio-preview"),
    ]
    for vendor, exp_class, exp_model in tests:
        memory_log.reset_mock()
        result = tested.audio2texter(
            Settings(
                llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
                llm_audio=VendorKey(vendor=vendor, api_key="audioKey"),
                structured_rfv=False,
                audit_llm=False,
                is_tuning=False,
                api_signing_key="theApiSigningKey",
                max_workers=3,
                send_progress=False,
                commands_policy=AccessPolicy(policy=False, items=[]),
                staffers_policy=AccessPolicy(policy=False, items=[]),
                cycle_transcript_overlap=37,
            ),
            memory_log,
        )
        assert memory_log.mock_calls == []
        assert isinstance(result, exp_class)
        assert result.api_key == "audioKey"
        assert result.model == exp_model
        assert result.memory_log == memory_log


def test_canvas_host():
    tests = [
        ("theCanvasInstance", "https://theCanvasInstance.canvasmedical.com"),
        ("local", "http://localhost:8000"),
    ]

    for canvas_instance, expected in tests:
        tested = Helper
        result = tested.canvas_host(canvas_instance)
        assert result == expected


def test_canvas_ws_host():
    tests = [
        ("theCanvasInstance", "wss://theCanvasInstance.canvasmedical.com"),
        ("local", "ws://localhost:8000"),
    ]

    for canvas_instance, expected in tests:
        tested = Helper
        result = tested.canvas_ws_host(canvas_instance)
        assert result == expected
