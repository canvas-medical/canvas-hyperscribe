import json
from http import HTTPStatus

from logger import log
from requests import post as requests_post

from hyperscribe.protocols.llms.llm_base import LlmBase
from hyperscribe.protocols.structures.http_response import HttpResponse


class LlmGoogle(LlmBase):

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({"format": f"audio/{audio_format}", "data": audio})

    def to_dict(self, audio_uris: list[tuple[str, str]]) -> dict:
        result = {
            "contents": [],
            "generationConfig": {"temperature": self.temperature},
        }
        roles = {
            self.ROLE_SYSTEM: "user",
            self.ROLE_USER: "user",
            self.ROLE_MODEL: "model",
        }
        for prompt in self.prompts:
            role = roles[prompt.role]
            part = {"text": "\n".join(prompt.text)}
            # contiguous parts for the same role are merged
            if result["contents"] and result["contents"][-1]["role"] == role:
                result["contents"][-1]["parts"].append(part)
            else:
                result["contents"].append({
                    "role": role,
                    "parts": [part],
                })
        # on the first part, add the audio, if any
        for mime, uri in audio_uris:
            result["contents"][0]["parts"].append({"file_data": {"mime_type": mime, "file_uri": uri}})

        return result

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

    def request(self, add_log: bool = False) -> HttpResponse:
        # audios are to be uploaded first (they are auto-deleted after 48h)
        audio_uris: list[tuple[str, str]] = [
            (audio["format"], uri)
            for idx, audio in enumerate(self.audios)
            if (uri := self.upload_audio(audio["data"], audio["format"], f"audio{idx:02d}"))
        ]

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
        result = HttpResponse(code=request.status_code, response=request.text)
        if result.code == HTTPStatus.OK.value:
            content = json.loads(request.text)
            text = content.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            result = HttpResponse(code=result.code, response=text)

        if add_log:
            log.info("***** CHAT STARTS ******")
            log.info(json.dumps(self.to_dict(audio_uris), indent=2))
            log.info(f"response code: >{request.status_code}<")
            log.info(request.text)
            log.info("****** CHAT ENDS *******")

        return result
