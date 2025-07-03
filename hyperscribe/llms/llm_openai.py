from __future__ import annotations

import json
from base64 import b64encode
from http import HTTPStatus

from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.memory_log import MemoryLog


class LlmOpenai(LlmBase):

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({
                "format": audio_format,
                "data": b64encode(audio).decode("utf-8"),
            })

    def to_dict(self, for_log: bool) -> dict:
        roles = {
            self.ROLE_SYSTEM: "system",  # <-- for o1 models it should be "developer"
            self.ROLE_USER: "user",
            self.ROLE_MODEL: "assistant",
        }
        messages: list[dict] = [
            {
                "role": roles[prompt.role],
                "content": [{"type": "text", "text": "\n".join(prompt.text)}],
            }
            for prompt in self.prompts
        ]
        # on the first user input, add the audio, if any
        for audio in self.audios:
            messages[1]["content"].append({
                "type": "input_audio",
                "input_audio": "some audio" if for_log else audio,
            })

        return {
            "model": self.model,
            "modalities": ["text"],
            "messages": messages,
            "temperature": self.temperature,
        }

    def request(self) -> HttpResponse:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "OpenAI-Beta": "assistants=v2",
        }
        data = json.dumps(self.to_dict(False))
        self.memory_log.log("--- request begins:")
        self.memory_log.log(json.dumps(self.to_dict(True), indent=2))
        request = requests_post(
            url,
            headers=headers,
            params={},
            data=data,
            verify=True,
            timeout=None,
        )
        self.memory_log.log(f"status code: {request.status_code}")
        self.memory_log.log(request.text)
        self.memory_log.log("--- request ends ---")
        result = HttpResponse(code=request.status_code, response=request.text)
        if result.code == HTTPStatus.OK.value:
            content = json.loads(request.text)
            text = content.get("choices", [{}])[0].get("message", {}).get("content", "")
            result = HttpResponse(code=result.code, response=text)

        return result

    def audio_to_text(self, audio: bytes) -> HttpResponse:
        default_model = "whisper-1"
        language = "en"
        response_format = "text"
        url = "https://api.openai.com/v1/audio/transcriptions"
        prompt = [
            "The conversation is in the medical context.",
        ]
        data = {
            "model": default_model,
            "language": language,
            "prompt": "\n".join(prompt),
            "response_format": response_format,
        }

        headers = {
            # "Content-Type": "multipart/form-data",
            "Authorization": f"Bearer {self.api_key}",
        }
        files = {"file": ("audio.mp3", audio, "application/octet-stream")}
        request = requests_post(
            url,
            headers=headers,
            params={},
            data=data,
            files=files,
            verify=True,
        )
        return HttpResponse(code=request.status_code, response=request.text)
    
# hyperscribe/llms/llm_openai.py
class LlmOpenai4o(LlmOpenai):
    """
    GPT-4o wrapper.
    Keeps everything from LlmOpenai but forces:
      • model = gpt-4o
      • modalities = ["text"]
      • temperature = what caller passes (defaults 0.0)
    """

    def __init__(
        self,
        memory_log: MemoryLog,
        api_key: str,
        *,
        with_audit: bool = False,
        temperature: float = 0.0,
    ):
        super().__init__(memory_log, api_key, Constants.OPENAI_CHAT_TEXT_4O, with_audit)
        self.temperature = temperature

    def to_dict(self, for_log: bool) -> dict:
        d = super().to_dict(for_log)
        d["modalities"] = ["text"]
        return d

