import json
from http import HTTPStatus

from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse


class LlmGoogle(LlmBase):
    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({"format": f"audio/{audio_format}", "data": audio})

    def to_dict(self, audio_uris: list[tuple[str, str]]) -> dict:
        contents: list[dict] = []
        roles = {self.ROLE_SYSTEM: "user", self.ROLE_USER: "user", self.ROLE_MODEL: "model"}
        for prompt in self.prompts:
            role = roles[prompt.role]
            part = {"text": "\n".join(prompt.text)}
            # contiguous parts for the same role are merged
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": role, "parts": [part]})
        # on the first part, add the audio, if any
        for mime, uri in audio_uris:
            contents[0]["parts"].append({"file_data": {"mime_type": mime, "file_uri": uri}})

        return {"contents": contents, "generationConfig": {"temperature": self.temperature}}

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

    def request(self) -> HttpResponse:
        # audios are to be uploaded first (they are auto-deleted after 48h)
        audio_uris: list[tuple[str, str]] = [
            (audio["format"], uri)
            for idx, audio in enumerate(self.audios)
            if (uri := self.upload_audio(audio["data"], audio["format"], f"audio{idx:02d}"))
        ]

        url = f"https://generativelanguage.googleapis.com/v1beta/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        data = json.dumps(self.to_dict(audio_uris))
        self.memory_log.log("--- request begins:")
        self.memory_log.log(json.dumps(self.to_dict(audio_uris), indent=2))
        request = requests_post(url, headers=headers, params={}, data=data, verify=True, timeout=None)
        self.memory_log.log(f"status code: {request.status_code}")
        self.memory_log.log(request.text)
        self.memory_log.log("--- request ends ---")
        result = HttpResponse(code=request.status_code, response=request.text)
        if result.code == HTTPStatus.OK.value:
            content = json.loads(request.text)
            text = content.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            result = HttpResponse(code=result.code, response=text)

        return result
