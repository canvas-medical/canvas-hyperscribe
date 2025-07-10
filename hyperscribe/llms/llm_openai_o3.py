from hyperscribe.llms.llm_openai import LlmOpenai
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class LlmOpenaiO3(LlmOpenai):
    """Defaults to text-only modalities (same as LlmOpenai4o)"""
    def __init__(
        self,
        memory_log: MemoryLog,
        api_key: str,
        *,
        with_audit: bool = False,
        temperature: float = 1.0,
    ):
        super().__init__(memory_log, api_key, Constants.OPENAI_CHAT_TEXT_O3, with_audit)
        self.temperature = temperature

    def to_dict(self, for_log: bool) -> dict:
        result = super().to_dict(for_log)
        result.pop("modalities", None)
        return result