from __future__ import annotations

from canvas_sdk.clients.llms import LlmOpenai as LlmOpenaiBase
from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts


class LlmOpenai(LlmOpenaiBase, LlmBase):
    def support_speaker_identification(self) -> bool:
        return True

    def audio_to_text(self, audio: bytes) -> HttpResponse:
        default_model = "whisper-1"
        language = "en"
        response_format = "text"
        url = "https://us.api.openai.com/v1/audio/transcriptions"
        prompt = ["The conversation is in the medical context."]
        data = {
            "model": default_model,
            "language": language,
            "prompt": "\n".join(prompt),
            "response_format": response_format,
        }

        headers = {
            # "Content-Type": "multipart/form-data",
            "Authorization": f"Bearer {self.settings.api_key}",
        }
        files = {"file": ("audio.mp3", audio, "application/octet-stream")}
        request = requests_post(url, headers=headers, params={}, data=data, files=files, verify=True)
        return HttpResponse(
            code=request.status_code,
            response=request.text,
            tokens=TokenCounts(prompt=0, generated=0),
        )
