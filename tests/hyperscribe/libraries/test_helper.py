from datetime import datetime, date
from enum import Enum
from unittest.mock import patch, call, MagicMock

import pytest
from canvas_sdk.clients.llms import LlmSettings
from canvas_sdk.clients.llms.structures.settings import (
    LlmSettingsGemini,
    LlmSettingsAnthropic,
    LlmSettingsGpt4,
    LlmSettingsGpt5,
)
from canvas_sdk.v1.data.note import NoteStateChangeEvent, NoteStates

from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.llms.llm_eleven_labs import LlmElevenLabs
from hyperscribe.llms.llm_google import LlmGoogle
from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.model_spec import ModelSpec
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


@patch.object(Settings, "llm_text_model")
def test_chatter(llm_text_model):
    memory_log = MagicMock()

    def reset_mocks():
        llm_text_model.reset_mock()
        memory_log.reset_mock()

    tested = Helper
    tests = [
        (
            "Anthropic",
            True,
            ["theModel"],
            LlmAnthropic,
            LlmSettingsAnthropic(api_key="textKey", model="theModel", temperature=0.0, max_tokens=64000),
        ),
        (
            "Google",
            True,
            ["theModel"],
            LlmGoogle,
            LlmSettingsGemini(api_key="textKey", model="theModel", temperature=0.0),
        ),
        ("Any", True, ["theModel"], LlmOpenai, LlmSettingsGpt4(api_key="textKey", model="theModel", temperature=0.0)),
        (
            "Anthropic",
            False,
            ["theModel"],
            LlmAnthropic,
            LlmSettingsAnthropic(api_key="textKey", model="theModel", temperature=0.0, max_tokens=64000),
        ),
        (
            "Google",
            False,
            ["theModel"],
            LlmGoogle,
            LlmSettingsGemini(api_key="textKey", model="theModel", temperature=0.0),
        ),
        ("Any", False, ["theModel"], LlmOpenai, LlmSettingsGpt4(api_key="textKey", model="theModel", temperature=0.0)),
        #
        (
            "Any",
            False,
            ["gpt-5.1xyz"],
            LlmOpenai,
            LlmSettingsGpt5(api_key="textKey", model="gpt-5.1xyz", reasoning_effort="none", text_verbosity="medium"),
        ),
        (
            "Any",
            True,
            ["gpt-5.1xyz"],
            LlmOpenai,
            LlmSettingsGpt5(api_key="textKey", model="gpt-5.1xyz", reasoning_effort="high", text_verbosity="high"),
        ),
        (
            "Any",
            False,
            ["o123"],
            LlmOpenai,
            LlmSettingsGpt5(api_key="textKey", model="o123", reasoning_effort="none", text_verbosity="medium"),
        ),
        (
            "Any",
            True,
            ["o123"],
            LlmOpenai,
            LlmSettingsGpt5(api_key="textKey", model="o123", reasoning_effort="high", text_verbosity="high"),
        ),
    ]
    for vendor, reasoning_llm, side_effect_llm_text_model, exp_class, exp_settings in tests:
        reset_mocks()
        settings = Settings(
            llm_text=VendorKey(vendor=vendor, api_key="textKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
            structured_rfv=False,
            audit_llm=False,
            reasoning_llm=reasoning_llm,
            custom_prompts=[],
            is_tuning=False,
            api_signing_key="theApiSigningKey",
            max_workers=3,
            hierarchical_detection_threshold=5,
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=37,
        )
        llm_text_model.side_effect = side_effect_llm_text_model

        result = tested.chatter(settings, memory_log, ModelSpec.SIMPLER)

        calls = [call(ModelSpec.SIMPLER)]
        assert llm_text_model.mock_calls == calls
        assert memory_log.mock_calls == []

        assert isinstance(result, exp_class)
        assert result.settings == exp_settings
        assert result.memory_log == memory_log
        assert result.with_audit is False


def test_audio2texter():
    memory_log = MagicMock()
    tested = Helper
    tests = [
        ("ElevenLabs", LlmElevenLabs, "scribe_v1"),
        ("Any", LlmElevenLabs, "scribe_v1"),
    ]
    for vendor, exp_class, exp_model in tests:
        memory_log.reset_mock()
        result = tested.audio2texter(
            Settings(
                llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
                llm_audio=VendorKey(vendor=vendor, api_key="audioKey"),
                structured_rfv=False,
                audit_llm=False,
                reasoning_llm=False,
                custom_prompts=[],
                is_tuning=False,
                api_signing_key="theApiSigningKey",
                max_workers=3,
                hierarchical_detection_threshold=5,
                send_progress=False,
                commands_policy=AccessPolicy(policy=False, items=[]),
                staffers_policy=AccessPolicy(policy=False, items=[]),
                trial_staffers_policy=AccessPolicy(policy=True, items=[]),
                cycle_transcript_overlap=37,
            ),
            memory_log,
        )
        assert memory_log.mock_calls == []
        assert isinstance(result, exp_class)
        exp_settings = LlmSettings(api_key="audioKey", model=exp_model)
        assert result.settings == exp_settings
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


@patch.object(NoteStateChangeEvent, "objects")
def test_editable_note(note_state_change_event_db):
    def reset_mocks():
        note_state_change_event_db.reset_mock()

    tested = Helper

    tests = [
        (NoteStateChangeEvent(state=NoteStates.NEW), True),
        (NoteStateChangeEvent(state=NoteStates.PUSHED), True),
        (NoteStateChangeEvent(state=NoteStates.UNLOCKED), True),
        (NoteStateChangeEvent(state=NoteStates.RESTORED), True),
        (NoteStateChangeEvent(state=NoteStates.UNDELETED), True),
        (NoteStateChangeEvent(state=NoteStates.CONVERTED), True),
        (NoteStateChangeEvent(state=NoteStates.LOCKED), False),
        (NoteStateChangeEvent(state=NoteStates.DELETED), False),
        (NoteStateChangeEvent(state=NoteStates.RELOCKED), False),
        (NoteStateChangeEvent(state=NoteStates.RECALLED), False),
        (NoteStateChangeEvent(state=NoteStates.DISCHARGED), False),
        (NoteStateChangeEvent(state=NoteStates.SCHEDULING), False),
        (NoteStateChangeEvent(state=NoteStates.BOOKED), False),
        (NoteStateChangeEvent(state=NoteStates.CANCELLED), False),
        (NoteStateChangeEvent(state=NoteStates.NOSHOW), False),
        (NoteStateChangeEvent(state=NoteStates.REVERTED), False),
        (NoteStateChangeEvent(state=NoteStates.CONFIRM_IMPORT), False),
        (None, False),
    ]
    for current_note, expected in tests:
        note_state_change_event_db.filter.return_value.order_by.return_value.last.side_effect = [current_note]
        result = tested.editable_note(778)
        assert result is expected
        calls = [
            call.filter(note_id=778),
            call.filter().order_by("created"),
            call.filter().order_by().last(),
        ]
        assert note_state_change_event_db.mock_calls == calls
        reset_mocks()
