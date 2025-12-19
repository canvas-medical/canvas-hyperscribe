from canvas_sdk.clients.llms import LlmAnthropic as LlmAnthropicBase

from hyperscribe.llms.llm_base import LlmBase


class LlmAnthropic(LlmAnthropicBase, LlmBase):
    def support_speaker_identification(self) -> bool:
        return True
