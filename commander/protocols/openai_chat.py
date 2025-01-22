import json
import re
from base64 import b64encode
from http import HTTPStatus

from logger import log
from requests import post as requests_post

from commander.protocols.structures.http_response import HttpResponse
from commander.protocols.structures.json_extract import JsonExtract


class OpenaiChat:
    ROLE_SYSTEM = "system"
    ROLE_USER = "user"

    def __init__(self, openai_key: str, model: str):
        self.openai_key = openai_key
        self.model = model
        self.temperature = 0.0
        self.system_prompt: list[str] = []
        self.user_prompt: list[str] = []
        self.audios: list[dict] = []

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({
                "format": audio_format,
                "data": b64encode(audio).decode("utf-8"),
            })

    def to_dict(self, for_log: bool = False) -> dict:
        content = [{
            "type": "text",
            "text": "\n".join(self.user_prompt),
        }]
        for audio in self.audios:
            content.append({
                "type": "input_audio",
                "input_audio": "some audio" if for_log else audio,
            })

        return {
            "model": self.model,
            "modalities": ["text"],
            "messages": [
                {"role": self.ROLE_SYSTEM, "content": "\n".join(self.system_prompt)},
                {"role": self.ROLE_USER, "content": content},
            ],
            "temperature": self.temperature,
        }

    def post(self, url: str, params: dict, data: str, timeout: int | None = None) -> HttpResponse:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_key}",
            "OpenAI-Beta": "assistants=v2",
        }
        request = requests_post(
            url,
            headers=headers,
            params=params,
            data=data,
            verify=True,
            timeout=timeout,
        )
        return HttpResponse(code=request.status_code, response=request.text)

    def chat(self, add_log: bool = False) -> JsonExtract:
        # TODO handle errors (network issue, incorrect LLM response format...)
        url = "https://api.openai.com/v1/chat/completions"
        response = self.post(url, {}, json.dumps(self.to_dict()))
        if response.code == HTTPStatus.OK.value:
            content = json.loads(response.response)
            text = content.get("choices", [{}])[0].get("message", {}).get("content", "")
            if add_log:
                log.info("***** CHAT STARTS ******")
                # log.info(self.to_dict(True))
                # log.info(f"   -------------    ")
                log.info(text)
                log.info("****** CHAT ENDS *******")
            return self.extract_json_from(text)
        else:
            log.info("***********")
            log.info(response.code)
            log.info(response.response)
            log.info("***********")
        return JsonExtract(f"the reported error is: {response.code}", True, [])

    @classmethod
    def extract_json_from(cls, content: str) -> JsonExtract:
        # print("-------------------------------------------------")
        # print(content)
        # print("-------------------------------------------------")
        result: list = []
        pattern_json = re.compile(r"```json\s*\n(.*?)\n\s*```", re.DOTALL | re.IGNORECASE)
        for embedded in pattern_json.finditer(content):
            try:
                result.append(json.loads(embedded.group(1)))
            except Exception as e:
                log.info(e)
                log.info("---->")
                log.info(embedded)
                log.info("<----")
                return JsonExtract(error=str(e), has_error=True, content=[])

        if not result:
            return JsonExtract(error="No JSON markdown found", has_error=True, content=[])

        if len(result) == 1:
            return JsonExtract(error="", has_error=False, content=result[0])
        return JsonExtract(error="", has_error=False, content=result)

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
            "Authorization": f"Bearer {self.openai_key}",
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
