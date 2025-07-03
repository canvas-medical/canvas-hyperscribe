import pytest
from datetime import datetime, date
from enum import Enum
from unittest.mock import patch, call, MagicMock

from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.llms.llm_google import LlmGoogle
from hyperscribe.llms.llm_openai import LlmOpenai, LlmOpenai4o
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.constants import Constants


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
    tests = [
        (None, None),
        (datetime(2025, 2, 4), date(2025, 2, 4)),
    ]
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
    tests = [
        ("I1234", "I12.34"),
        ("I12", "I12"),
        ("I1", "I1"),
        ("I123", "I12.3"),
    ]
    for code, expected in tests:
        result = tested.icd10_add_dot(code)
        assert result == expected, f"---> {code}"


def test_icd10_strip_dot():
    tested = Helper
    tests = [
        ("I12.34", "I1234"),
        ("I12", "I12"),
        ("I123", "I123"),
    ]
    for code, expected in tests:
        result = tested.icd10_strip_dot(code)
        assert result == expected, f"---> {code}"


def test_chatter():
    memory_log = MagicMock()
    tested = Helper
    tests = [
        ("Anthropic", LlmAnthropic, "claude-3-5-sonnet-20241022"),
        ("Google", LlmGoogle, "models/gemini-2.0-flash"),
        ("Any", LlmOpenai, "o3"),
    ]
    for vendor, exp_class, exp_model in tests:
        memory_log.reset_mock()
        result = tested.chatter(Settings(
            llm_text=VendorKey(vendor=vendor, api_key="textKey"),
            llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
            science_host="scienceHost",
            ontologies_host="ontologiesHost",
            pre_shared_key="preSharedKey",
            structured_rfv=False,
            audit_llm=False,
            is_tuning=False,

            api_signing_key="theApiSigningKey",
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
        ), memory_log)
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
        ("Any", LlmOpenai, "gpt-4o-audio-preview"),
    ]
    for vendor, exp_class, exp_model in tests:
        memory_log.reset_mock()
        result = tested.audio2texter(Settings(
            llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
            llm_audio=VendorKey(vendor=vendor, api_key="audioKey"),
            science_host="scienceHost",
            ontologies_host="ontologiesHost",
            pre_shared_key="preSharedKey",
            structured_rfv=False,
            audit_llm=False,
            is_tuning=False,

            api_signing_key="theApiSigningKey",
            send_progress=False,
            commands_policy=AccessPolicy(policy=False, items=[]),
            staffers_policy=AccessPolicy(policy=False, items=[]),
        ), memory_log)
        assert memory_log.mock_calls == []
        assert isinstance(result, exp_class)
        assert result.api_key == "audioKey"
        assert result.model == exp_model
        assert result.memory_log == memory_log

class DummyVendorKey:
    def __init__(self, vendor: str, api_key: str, model: str, temperature: float):
        self.vendor = vendor
        self.api_key = api_key
        self.model = model
        self.temperature = temperature

class DummySettings:
    def __init__(self, vendor: str, api_key: str, model: str, temperature: float, audit_llm: bool):
        self.llm_text = DummyVendorKey(vendor, api_key, model, temperature)
        self.audit_llm = audit_llm

@pytest.mark.parametrize("model_name", [
    Constants.OPENAI_CHAT_TEXT_4O,
    Constants.OPENAI_CHAT_TEXT_4O.lower(),
    "gpt-4o",
    "4o",
])
def test_chatter_for_openai_4o_variants(model_name):
    memory_log = MagicMock()
    settings = DummySettings(
        vendor="SomeVendor",
        api_key="test-api-key",
        model=model_name,
        temperature=0.42,
        audit_llm=True,
    )
    client = Helper.chatter(settings, memory_log)
    assert isinstance(client, LlmOpenai4o)
    assert client.api_key == "test-api-key"
    assert client.model == model_name
    assert client.with_audit is True
    assert client.temperature == 0.42
    memory_log.assert_not_called()
