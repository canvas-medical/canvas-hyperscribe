from __future__ import annotations

import json
import re
from abc import ABC
from http import HTTPStatus
from time import time

from canvas_sdk.clients.llms import LlmSettings
from canvas_sdk.clients.llms.libraries import LlmApi
from canvas_sdk.questionnaires.utils import Draft7Validator
from logger import log

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.json_extract import JsonExtract
from hyperscribe.structures.llm_turn import LlmTurn


class LlmBase(LlmApi, ABC):

    def __init__(self, settings: LlmSettings, memory_log: MemoryLog, with_audit: bool):
        super().__init__(settings, memory_log)
        self.memory_log = memory_log
        self.with_audit = with_audit
        self.audios: list[dict] = []

    def support_speaker_identification(self) -> bool:
        raise NotImplementedError()

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        raise NotImplementedError()

    def chat(self, schemas: list) -> JsonExtract:
        self.memory_log.log("-- CHAT BEGINS --")
        attempts = 0
        start = time()
        for _ in range(Constants.MAX_ATTEMPTS_LLM_JSON):
            attempts += 1
            responses = self.attempt_requests(Constants.MAX_ATTEMPTS_LLM_HTTP)
            # http error
            if responses and responses[-1].code != HTTPStatus.OK:
                result = JsonExtract(has_error=True, error=responses[-1].response, content=[])
                break

            result = self.extract_json_from(responses[-1].response, schemas)
            self.memory_log.add_consumption(responses[-1].tokens)
            if not result.has_error:
                self.memory_log.log("result->>")
                self.memory_log.log(json.dumps(result.content, indent=2))
                self.memory_log.log("<<-")
                break

            # JSON error
            self.set_model_prompt(responses[-1].response.splitlines())
            self.set_user_prompt(
                [
                    "Your previous response has the following errors:",
                    "```text",
                    result.error,
                    "```",
                    "",
                    "Please, correct your answer following rigorously the initial request and "
                    "the mandatory response format.",
                ],
            )
        else:
            result = JsonExtract(
                has_error=True,
                error=f"JSON incorrect: max attempts ({Constants.MAX_ATTEMPTS_LLM_JSON}) exceeded",
                content=[],
            )
            self.memory_log.log(f"error: {result.error}")

        self.memory_log.log(f"--- CHAT ENDS - {attempts} attempts - {int((time() - start) * 1000)}ms ---")
        self.memory_log.store_so_far()
        return result

    def single_conversation(
            self,
            system_prompt: list[str],
            user_prompt: list[str],
            schemas: list,
            instruction: Instruction | None,
    ) -> list:
        used_schemas = [s for s in schemas]
        used_prompt = [s for s in user_prompt]

        # self.reset_prompts()
        self.set_system_prompt(system_prompt)
        self.set_user_prompt(used_prompt)
        response = self.chat(used_schemas)
        if response.has_error is False and response.content:
            result = response.content
            if len(schemas) == 1:
                result = result[0]
            self.store_llm_turns(result, instruction)
            return result
        return []

    def store_llm_turns(self, model_prompt: list[str], instruction: Instruction | None) -> None:
        if not self.with_audit:
            return
        label = self.memory_log.label
        index = -1
        if instruction is not None:
            label = instruction.instruction
            index = instruction.index

        turns = [turn for turn in self.prompts]
        turns.append(LlmTurn(role=self.ROLE_MODEL, text=["```json", json.dumps(model_prompt), "```"]))

        LlmTurnsStore.instance(self.memory_log.s3_credentials, self.memory_log.identification).store(
            label,
            index,
            turns,
        )

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
            return JsonExtract(
                error="No JSON markdown found. "
                      "The response should be enclosed within a JSON Markdown block like: \n"
                      "```json\nJSON OUTPUT HERE\n```",
                has_error=True,
                content=[],
            )

        # check against the schemas
        for idx, (returned, validation) in enumerate(zip(result, schemas or [])):
            if problems := cls.json_validator(returned, validation):
                return JsonExtract(error=f"in the JSON #{idx + 1}:{problems}", has_error=True, content=[])

        if len(result) < len(schemas):
            return JsonExtract(error=f"{len(schemas)} JSON markdown blocks are expected", has_error=True, content=[])

        # all good
        return JsonExtract(error="", has_error=False, content=result)
