from unittest.mock import MagicMock

from canvas_sdk.clients.llms import LlmAnthropic as LlmAnthropicBase, LlmSettings

from hyperscribe.llms.llm_anthropic import LlmAnthropic
from hyperscribe.llms.llm_base import LlmBase


def test_class():
    assert issubclass(LlmAnthropic, LlmAnthropicBase)
    assert issubclass(LlmAnthropic, LlmBase)


def test_support_speaker_identification():
    llm_settings = LlmSettings(api_key="theKey", model="theModel")
    memory_log = MagicMock()
    tested = LlmAnthropic(llm_settings, memory_log, False)
    result = tested.support_speaker_identification()
    assert result is True
