import json
from http import HTTPStatus

from canvas_sdk.clients.llms import LlmResponse, LlmTokens
from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase


class LlmElevenLabs(LlmBase):
    def support_speaker_identification(self) -> bool:
        return False

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({"data": audio})

    @classmethod
    def _api_base_url(cls) -> str:
        return "https://api.elevenlabs.io/v1/speech-to-text"

    def request(self) -> LlmResponse:
        if not self.audios:
            return LlmResponse(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                response="no audio provided",
                tokens=LlmTokens(prompt=0, generated=0),
            )
        headers = {
            "xi-api-key": self.settings.api_key,
        }
        data = {
            "model_id": self.settings.model,
            "diarize": True,
            "temperature": 0,
        }
        self.memory_log.log("--- request begins:")
        request = requests_post(
            self._api_base_url(),
            headers=headers,
            params={},
            data=data,
            files={"file": self.audios[0]["data"]},
            verify=True,
            timeout=None,
        )
        self.memory_log.log(f"status code: {request.status_code}")
        self.memory_log.log(request.json())
        self.memory_log.log("--- request ends ---")
        result = LlmResponse(
            code=HTTPStatus(request.status_code),
            response=request.text,
            tokens=LlmTokens(prompt=0, generated=0),
        )
        if result.code == HTTPStatus.OK:
            turns: list[dict] = []
            for words in request.json()["words"]:
                if not turns or words["speaker_id"] != turns[-1]["speaker_id"]:
                    turns.append(
                        {
                            "speaker_id": words["speaker_id"],
                            "text": [],
                            "start": words["start"],
                            "end": words["end"],
                        }
                    )
                turns[-1]["end"] = words["end"]
                if words["type"] == "word":
                    turns[-1]["text"].append(words["text"])
                elif words["type"] == "spacing":
                    turns[-1]["text"].append(" ")

            if not turns:
                turns = [{"speaker_id": "speaker_0", "text": [], "start": 0.0, "end": 0.0}]

            result = LlmResponse(
                code=result.code,
                response="\n".join(
                    [
                        "```json",
                        json.dumps(
                            [
                                {
                                    "speaker": t["speaker_id"],
                                    "text": "".join(t["text"]) or "[silence]",
                                    "start": t["start"],
                                    "end": t["end"],
                                }
                                for t in turns
                            ],
                            indent=1,
                        ),
                        "```",
                    ]
                ),
                tokens=LlmTokens(prompt=0, generated=0),
            )

        return result
