from canvas_sdk.clients.llms import LlmGoogle as LlmGoogleBase

from hyperscribe.llms.llm_base import LlmBase


class LlmGoogle(LlmGoogleBase, LlmBase):
    def support_speaker_identification(self) -> bool:
        return True
