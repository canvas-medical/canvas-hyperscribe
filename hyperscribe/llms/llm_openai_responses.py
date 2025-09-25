from __future__ import annotations

import json
from http import HTTPStatus

from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse


class LlmOpenaiResponses(LlmBase):
    def support_speaker_identification(self) -> bool:
        return False

    def to_dict(self) -> dict:
        roles = {
            self.ROLE_SYSTEM: "developer",
            self.ROLE_USER: "user",
            self.ROLE_MODEL: "assistant",
        }
        messages: list[dict] = [
            {
                "role": roles[prompt.role],
                "content": [
                    {
                        "type": "input_text" if prompt.role == self.ROLE_USER else "output_text",
                        "text": "\n".join(prompt.text),
                    }
                ],
            }
            for prompt in self.prompts
            if prompt.role != self.ROLE_SYSTEM
        ]

        system_prompt = ["\n".join(prompt.text) for prompt in self.prompts if prompt.role == self.ROLE_SYSTEM]
        extras = {}
        if not self.model.startswith("gpt-5"):
            extras = {
                "modalities": ["text"],
                "temperature": self.temperature,
            }
        return {
            "model": self.model,
            "instructions": "\n".join(system_prompt),
            "input": messages,
        } | extras

    def request(self) -> HttpResponse:
        url = "https://us.api.openai.com/v1/responses"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        data = json.dumps(self.to_dict())
        self.memory_log.log("--- request begins:")
        self.memory_log.log(json.dumps(self.to_dict(), indent=2))
        request = requests_post(url, headers=headers, params={}, data=data, verify=True, timeout=None)
        self.memory_log.log(f"status code: {request.status_code}")
        self.memory_log.log(request.text)
        self.memory_log.log("--- request ends ---")
        result = HttpResponse(code=request.status_code, response=request.text)
        if result.code == HTTPStatus.OK.value:
            content = json.loads(request.text)
            text = ""
            for output in content.get("output", [{}]):
                if output.get("type", "") == "message":
                    text += output.get("content", [{}])[0].get("text", "")
            result = HttpResponse(code=result.code, response=text)

        return result
