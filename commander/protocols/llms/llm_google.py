import json
from http import HTTPStatus

from logger import log
from requests import post as requests_post

from commander.protocols.llms.llm_base import LlmBase
from commander.protocols.structures.http_response import HttpResponse
from commander.protocols.structures.json_extract import JsonExtract


class LlmGoogle(LlmBase):
    ROLE_SYSTEM = "system"
    ROLE_USER = "user"

    def to_dict(self, for_log: bool = False) -> dict:
        return {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": "\n".join(self.system_prompt)},
                        {"text": "\n".join(self.user_prompt)},
                    ],
                },
            ],
            "generationConfig": {"temperature": self.temperature},
        }

    def chat(self, add_log: bool = False, schemas: list | None = None) -> JsonExtract:
        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        data = json.dumps(self.to_dict())
        request = requests_post(
            url,
            headers=headers,
            params={},
            data=data,
            verify=True,
            timeout=None,
        )
        response = HttpResponse(code=request.status_code, response=request.text)
        if response.code == HTTPStatus.OK.value:
            content = json.loads(response.response)
            text = content.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if add_log:
                log.info("***** CHAT STARTS ******")
                # log.info(self.to_dict(True))
                # log.info(f"   -------------    ")
                log.info(text)
                log.info("****** CHAT ENDS *******")
            return self.extract_json_from(text, schemas)
        else:
            log.info("***********")
            log.info(response.code)
            log.info(response.response)
            log.info("***********")
        return JsonExtract(f"the reported error is: {response.code}", True, [])
