import json
from http import HTTPStatus

from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse


class LlmAnthropic(LlmBase):

    def to_dict(self) -> dict:
        messages: list[dict] = []

        roles = {
            self.ROLE_SYSTEM: "user",
            self.ROLE_USER: "user",
            self.ROLE_MODEL: "assistant",
        }
        for prompt in self.prompts:
            role = roles[prompt.role]
            part = {"type": "text", "text": "\n".join(prompt.text)}
            # contiguous parts for the same role are merged
            if messages and messages[-1]["role"] == role:
                messages[-1]["content"].append(part)
            else:
                messages.append({
                    "role": role,
                    "content": [part],
                })

        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": 8192,
            "messages": messages,
        }

    def request(self) -> HttpResponse:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
        }
        data = json.dumps(self.to_dict())
        self.memory_log.log("--- request begins:")
        self.memory_log.log(json.dumps(self.to_dict(), indent=2))
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
            text = content.get("content", [{}])[0].get("text", "")
            result = HttpResponse(code=result.code, response=text)

        return result
