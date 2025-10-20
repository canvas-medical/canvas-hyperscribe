from unittest.mock import patch, call

import pytest

from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_namedtuple


def test_class():
    tested = Settings
    fields = {
        "llm_text": VendorKey,
        "llm_audio": VendorKey,
        "structured_rfv": bool,
        "audit_llm": bool,
        "reasoning_llm": bool,
        "is_tuning": bool,
        "max_workers": int,
        "api_signing_key": str,
        "send_progress": bool,
        "commands_policy": AccessPolicy,
        "staffers_policy": AccessPolicy,
        "trial_staffers_policy": AccessPolicy,
        "cycle_transcript_overlap": int,
    }
    assert is_namedtuple(tested, fields)


@patch.object(Settings, "_from_dict_base")
def test_from_dictionary(from_dict_base):
    def reset_mocks():
        from_dict_base.reset_mock()

    tested = Settings
    from_dict_base.side_effect = ["theSetting"]
    dictionary = {"variable1": "value1", "variable2": "value2"}
    result = tested.from_dictionary(dictionary)
    expected = "theSetting"
    assert result == expected

    calls = [call(dictionary, False)]
    assert from_dict_base.mock_calls == calls
    reset_mocks()


@patch.object(Settings, "_from_dict_base")
def test_from_dictionary(from_dict_base):
    def reset_mocks():
        from_dict_base.reset_mock()

    tested = Settings
    tests = [
        ({"variable1": "value1", "variable2": "value2"}, False),
        ({"variable1": "value1", "TextModelType": "something"}, False),
        ({"variable1": "value1", "TextModelType": "reasoning"}, True),
    ]
    for dictionary, exp_reasoning_llm in tests:
        from_dict_base.side_effect = ["theSetting"]
        result = tested.from_dict_with_reasoning(dictionary)
        expected = "theSetting"
        assert result == expected

        calls = [call(dictionary, exp_reasoning_llm)]
        assert from_dict_base.mock_calls == calls
        reset_mocks()


@patch.object(Settings, "clamp_int")
@patch.object(Settings, "is_true")
def test__from_dict_base(is_true, clamp_int):
    def reset_mocks():
        is_true.reset_mock()
        clamp_int.reset_mock()

    tested = Settings

    tests = [
        (True, True, True, False, True, True),
        (True, False, True, False, False, False),
        (False, True, False, True, True, False),
        (False, False, False, True, False, True),
    ]
    for rfv, audit, commands, staffers, progress, tuning in tests:
        is_true.side_effect = [rfv, audit, tuning, commands, staffers]
        clamp_int.side_effect = [7, 54]
        result = tested._from_dict_base(
            {
                "VendorTextLLM": "textVendor",
                "KeyTextLLM": "textAPIKey",
                "VendorAudioLLM": "audioVendor",
                "KeyAudioLLM": "audioAPIKey",
                "StructuredReasonForVisit": "rfv",
                "AuditLLMDecisions": "audit",
                "IsTuning": "tuning",
                "APISigningKey": "theApiSigningKey",
                "sendProgress": progress,
                "CommandsList": "ReasonForVisit,StopMedication Task Vitals",
                "CommandsPolicy": "commands",
                "StaffersList": "47 32",
                "StaffersPolicy": "staffers",
                "CycleTranscriptOverlap": "57",
                "MaxWorkers": "4",
            },
            False,
        )
        expected = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            structured_rfv=rfv,
            audit_llm=audit,
            reasoning_llm=False,
            is_tuning=tuning,
            api_signing_key="theApiSigningKey",
            max_workers=7,
            send_progress=progress,
            commands_policy=AccessPolicy(policy=commands, items=["ReasonForVisit", "StopMedication", "Task", "Vitals"]),
            staffers_policy=AccessPolicy(policy=staffers, items=["32", "47"]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=54,
        )
        assert result == expected
        calls = [call("rfv"), call("audit"), call("tuning"), call("commands"), call("staffers")]
        assert is_true.mock_calls == calls
        calls = [
            call("4", 1, 10, 3),
            call("57", 5, 250, 100),
        ]
        assert clamp_int.mock_calls == calls
        reset_mocks()

    # missing key
    with pytest.raises(KeyError):
        _ = tested._from_dict_base({}, False)

    # cycle_transcript_overlap
    overlap_tests = [("0", 5), ("1", 5), ("5", 5), ("6", 6), ("249", 249), ("250", 250), ("251", 250), ("251", 250)]
    for overlap, exp_overlap in overlap_tests:
        is_true.side_effect = [False, False, False, False, False]
        clamp_int.side_effect = [6, exp_overlap]
        result = tested._from_dict_base(
            {
                "VendorTextLLM": "textVendor",
                "KeyTextLLM": "textAPIKey",
                "VendorAudioLLM": "audioVendor",
                "KeyAudioLLM": "audioAPIKey",
                "APISigningKey": "theApiSigningKey",
                "CycleTranscriptOverlap": overlap,
            },
            True,
        )
        expected = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            structured_rfv=False,
            audit_llm=False,
            reasoning_llm=True,
            is_tuning=False,
            api_signing_key="theApiSigningKey",
            max_workers=6,
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=exp_overlap,
        )
        assert result == expected
        calls = [call(None), call(None), call(None), call(None), call(None)]
        assert is_true.mock_calls == calls
        calls = [
            call(None, 1, 10, 3),
            call(overlap, 5, 250, 100),
        ]
        assert clamp_int.mock_calls == calls
        reset_mocks()


def test_clamp_int():
    tests = [("9", 3, 8, 5, 8), ("1", 3, 8, 5, 3), ("6", 3, 8, 5, 6), ("a", 3, 8, 5, 5), (4, 3, 8, 5, 4)]
    tested = Settings
    for value, low, high, default, expected in tests:
        result = tested.clamp_int(value, low, high, default)
        assert result == expected, f"---> {value}"


def test_is_true():
    tested = Settings
    tests = [
        ("", False),
        ("yes", True),
        ("YES", True),
        ("y", True),
        ("Y", True),
        ("1", True),
        ("0", False),
        ("anything", False),
    ]
    for string, expected in tests:
        result = tested.is_true(string)
        assert result == expected, f"---> {string}"


def test_list_from():
    tested = Settings
    tests = [
        ("", []),
        ("command", ["command"]),
        (
            "command1 command2    command3, command4,,command5\ncommand6",
            ["command1", "command2", "command3", "command4", "command5", "command6"],
        ),
    ]
    for string, expected in tests:
        result = tested.list_from(string)
        assert result == expected, f"---> {string}"


def test_llm_audio_model():
    tests = [
        ("", "gpt-4o-audio-preview"),
        ("Anthropic", "gpt-4o-audio-preview"),
        ("ElevenLabs", "scribe_v1"),
        ("Google", "models/gemini-2.0-flash"),
        ("OpenAI", "gpt-4o-audio-preview"),
        ("Other", "gpt-4o-audio-preview"),
    ]
    for vendor, expected in tests:
        tested = Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor=vendor, api_key="audioAPIKey"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=False,
            is_tuning=True,
            api_signing_key="theApiSigningKey",
            max_workers=3,
            send_progress=True,
            commands_policy=AccessPolicy(policy=True, items=[]),
            staffers_policy=AccessPolicy(policy=True, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=54,
        )
        result = tested.llm_audio_model()
        assert result == expected, f"---> {vendor}"


def test_llm_text_model():
    tests = [
        ("", True, "o3"),
        ("Anthropic", True, "claude-3-5-sonnet-20241022"),
        ("Google", True, "models/gemini-2.0-flash"),
        ("OpenAI", True, "o3"),
        ("Other", True, "o3"),
        ("", False, "gpt-4o"),
        ("Anthropic", False, "claude-3-5-sonnet-20241022"),
        ("Google", False, "models/gemini-2.0-flash"),
        ("OpenAI", False, "gpt-4o"),
        ("Other", False, "gpt-4o"),
    ]
    for vendor, reasoning_llm, expected in tests:
        tested = Settings(
            llm_text=VendorKey(vendor=vendor, api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioAPIKey"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=reasoning_llm,
            is_tuning=True,
            api_signing_key="theApiSigningKey",
            max_workers=3,
            send_progress=True,
            commands_policy=AccessPolicy(policy=True, items=[]),
            staffers_policy=AccessPolicy(policy=True, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=54,
        )
        result = tested.llm_text_model()
        assert result == expected, f"---> {vendor}"


@patch.object(Settings, "llm_text_model")
def test_llm_text_temperature(llm_text_model):
    def reset_mocks():
        llm_text_model.reset_mock()

    tests = [
        ("claude-3-5-sonnet-20241022", 0.0),
        ("models/gemini-2.0-flash", 0.0),
        ("gpt-4o", 0.0),
        ("o3", 1.0),
        ("any", 0.0),
    ]
    for model, expected in tests:
        llm_text_model.side_effect = [model]
        tested = Settings(
            llm_text=VendorKey(vendor="theVendor", api_key="textAPIKey"),
            llm_audio=VendorKey(vendor="theVendor", api_key="audioAPIKey"),
            structured_rfv=True,
            audit_llm=True,
            reasoning_llm=True,
            is_tuning=True,
            api_signing_key="theApiSigningKey",
            max_workers=3,
            send_progress=True,
            commands_policy=AccessPolicy(policy=True, items=[]),
            staffers_policy=AccessPolicy(policy=True, items=[]),
            trial_staffers_policy=AccessPolicy(policy=True, items=[]),
            cycle_transcript_overlap=54,
        )
        result = tested.llm_text_temperature()
        assert result == expected, f"---> {model}"

        calls = [call()]
        assert llm_text_model.mock_calls == calls
        reset_mocks()
