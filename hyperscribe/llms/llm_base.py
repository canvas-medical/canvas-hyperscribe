from __future__ import annotations

import json
import re
from http import HTTPStatus

from canvas_sdk.questionnaires.utils import Draft7Validator
from logger import log

from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.llm_turn import LlmTurn


class LlmBase:
    ROLE_SYSTEM = "system"
    ROLE_USER = "user"
    ROLE_MODEL = "model"

    def __init__(self, memory_log: MemoryLog, api_key: str, model: str):
        self.memory_log = memory_log
        self.api_key = api_key
        self.model = model
        self.temperature = 0.0
        self.prompts: list[LlmTurn] = []
        self.audios: list[dict] = []

    def set_system_prompt(self, text: list[str]) -> None:
        prompt = LlmTurn(role=self.ROLE_SYSTEM, text=text)
        if self.prompts and self.prompts[0].role == LlmBase.ROLE_SYSTEM:
            self.prompts[0] = prompt
        else:
            self.prompts.insert(0, prompt)

    def set_user_prompt(self, text: list[str]) -> None:
        self.prompts.append(LlmTurn(role=self.ROLE_USER, text=text))

    def set_model_prompt(self, text: list[str]) -> None:
        self.prompts.append(LlmTurn(role=self.ROLE_MODEL, text=text))

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        raise NotImplementedError()

    def request(self) -> HttpResponse:
        raise NotImplementedError()

    def attempt_requests(self, attempts: int) -> HttpResponse:
        for _ in range(attempts):
            result = self.request()
            if result.code == HTTPStatus.OK.value:
                break
        else:
            result = HttpResponse(
                code=HTTPStatus.TOO_MANY_REQUESTS,
                response=f"Http error: max attempts ({attempts}) exceeded",
            )
            self.memory_log.log(f"error: {result.response}")
        return result

    def chat(self, schemas: list) -> JsonExtract:
        self.memory_log.log("-- CHAT BEGINS --")
        for _ in range(Constants.MAX_ATTEMPTS_LLM_JSON):
            response = self.attempt_requests(Constants.MAX_ATTEMPTS_LLM_HTTP)
            # http error
            if response.code != HTTPStatus.OK.value:
                result = JsonExtract(has_error=True, error=response.response, content=[])
                break

            result = self.extract_json_from(response.response, schemas)
            if result.has_error is False:
                self.memory_log.log("result->>")
                self.memory_log.log(json.dumps(result.content, indent=2))
                self.memory_log.log("<<-")
                break

            # JSON error
            self.set_model_prompt(response.response.splitlines())
            self.set_user_prompt([
                "Your previous response has the following errors:",
                "```text",
                result.error,
                "```",
                "",
                "Please, correct your answer following rigorously the initial request and the mandatory response format."
            ])
        else:
            result = JsonExtract(
                has_error=True,
                error=f"JSON incorrect: max attempts ({Constants.MAX_ATTEMPTS_LLM_JSON}) exceeded",
                content=[],
            )
            self.memory_log.log(f"error: {result.error}")

        self.memory_log.log("--- CHAT ENDS ---")
        self.memory_log.store_so_far()
        return result

    def single_conversation(self, system_prompt: list[str], user_prompt: list[str], schemas: list) -> list:
        self.set_system_prompt(system_prompt)
        self.set_user_prompt(user_prompt)
        response = self.chat(schemas)
        if response.has_error is False and response.content:
            return response.content
        return []

    @classmethod
    def json_validator(cls, response: list, json_schema: dict) -> str:
        result: list = []
        for error in Draft7Validator(json_schema).iter_errors(response):
            # assert isinstance(error, ValidationError)
            message = error.message
            if error.path:
                message = f"{error.message}, in path {list(error.path)}"
            result.append(message)

        return "\n".join(result)

    @classmethod
    def extract_json_from(cls, content: str, schemas: list) -> JsonExtract:
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

        # check against the schemas
        for idx, (returned, validation) in enumerate(zip(result, schemas or [])):
            if problems := cls.json_validator(returned, validation):
                return JsonExtract(error=f"in the JSON #{idx + 1}:{problems}", has_error=True, content=[])

        # all good
        if len(result) == 1:
            return JsonExtract(error="", has_error=False, content=result[0])
        return JsonExtract(error="", has_error=False, content=result)
