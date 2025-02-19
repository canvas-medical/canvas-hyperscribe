from __future__ import annotations

import json
import re

from logger import log

from commander.protocols.structures.json_extract import JsonExtract


class LlmBase:

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.temperature = 0.0
        self.system_prompt: list[str] = []
        self.user_prompt: list[str] = []
        self.audios: list[dict] = []

    def set_system_prompt(self, system_prompt: list[str]) -> None:
        self.system_prompt = system_prompt

    def set_user_prompt(self, user_prompt: list[str]) -> None:
        self.user_prompt = user_prompt

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        raise NotImplementedError()

    def chat(self, add_log: bool = False, schemas: list | None = None) -> JsonExtract:
        raise NotImplementedError()

    def single_conversation(self, system_prompt: list[str], user_prompt: list[str]) -> list:
        self.set_system_prompt(system_prompt)
        self.set_user_prompt(user_prompt)
        response = self.chat()
        if response.has_error is False and response.content:
            return response.content
        return []

    @classmethod
    def extract_json_from(cls, content: str, schemas: list | None = None) -> JsonExtract:
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
