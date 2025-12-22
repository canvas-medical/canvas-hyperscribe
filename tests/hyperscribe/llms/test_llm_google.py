from unittest.mock import MagicMock

from canvas_sdk.clients.llms import LlmGoogle as LlmGoogleBase
from canvas_sdk.clients.llms import LlmSettings

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.llms.llm_google import LlmGoogle


def test_class():
    assert issubclass(LlmGoogle, LlmGoogleBase)
    assert issubclass(LlmGoogle, LlmBase)


def test_support_speaker_identification():
    llm_settings = LlmSettings(api_key="theKey", model="theModel")
    memory_log = MagicMock()
    tested = LlmGoogle(llm_settings, memory_log, False)
    result = tested.support_speaker_identification()
    assert result is True
