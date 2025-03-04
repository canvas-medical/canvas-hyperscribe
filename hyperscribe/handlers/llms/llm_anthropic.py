import json
from http import HTTPStatus

from logger import log
from requests import post as requests_post

from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.http_response import HttpResponse


class LlmAnthropic(LlmBase):

    def to_dict(self) -> dict:
        result = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": 8192,
            "messages": [],
        }

        roles = {
            self.ROLE_SYSTEM: "user",
            self.ROLE_USER: "user",
            self.ROLE_MODEL: "assistant",
        }
        for prompt in self.prompts:
            role = roles[prompt.role]
            part = {"type": "text", "text": "\n".join(prompt.text)}
            # contiguous parts for the same role are merged
            if result["messages"] and result["messages"][-1]["role"] == role:
                result["messages"][-1]["content"].append(part)
            else:
                result["messages"].append({
                    "role": role,
                    "content": [part],
                })

        return result

    def request(self, add_log: bool = False) -> HttpResponse:
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.api_key,
        }
        data = json.dumps(self.to_dict())
        request = requests_post(
            url,
            headers=headers,
            params={},
            data=data,
            verify=True,
            timeout=None,
        )
        result = HttpResponse(code=request.status_code, response=request.text)
        if result.code == HTTPStatus.OK.value:
            content = json.loads(request.text)
            text = content.get("content", [{}])[0].get("text", "")
            result = HttpResponse(code=result.code, response=text)

        if add_log:
            log.info("***** CHAT STARTS ******")
            log.info(json.dumps(self.to_dict(), indent=2))
            log.info(f"response code: >{request.status_code}<")
            log.info(request.text)
            log.info("****** CHAT ENDS *******")

        return result
