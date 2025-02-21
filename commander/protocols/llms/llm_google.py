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

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({"format": f"audio/{audio_format}", "data": audio})

    def to_dict(self, audio_uris: dict[str, str]) -> dict:
        parts = [
            {"text": "\n".join(self.system_prompt)},
            {"text": "\n".join(self.user_prompt)},
        ]
        for mime, uri in audio_uris.items():
            parts.append({"file_data": {"mime_type": mime, "file_uri": uri}})

        return {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": self.temperature},
        }

    def upload_audio(self, audio: bytes, audio_format: str, audio_name: str) -> str:
        result = ""
        # get the URI
        url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={self.api_key}"
        headers = {
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(audio)),
            "X-Goog-Upload-Header-Content-Type": audio_format,
            "Content-Type": "application/json",
        }
        data = json.dumps({"file": {"display_name": audio_name}})
        request = requests_post(url, headers=headers, data=data, verify=True, timeout=None)
        if request.status_code == HTTPStatus.OK.value:
            # upload the file
            headers = {
                "Content-Length": str(len(audio)),
                "X-Goog-Upload-Offset": str(0),
                "X-Goog-Upload-Command": "upload, finalize",
            }
            url = request.headers["x-goog-upload-url"]
            request = requests_post(url, headers=headers, params={}, data=audio, verify=True, timeout=None)
            if request.status_code == HTTPStatus.OK.value:
                content = json.loads(request.text)
                result = content["file"]["uri"]

        return result

    def chat(self, add_log: bool = False, schemas: list | None = None) -> JsonExtract:
        # audios are to be uploaded first (they are auto-deleted after 48h)
        audio_uris: dict[str, str] = {
            audio["format"]: uri
            for idx, audio in enumerate(self.audios)
            if (uri := self.upload_audio(audio["data"], audio["format"], f"audio{idx:02d}"))
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        data = json.dumps(self.to_dict(audio_uris))
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
