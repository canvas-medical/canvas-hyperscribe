import json
from http import HTTPStatus

from requests import post as requests_post

from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts


class LlmElevenLabs(LlmBase):
    def support_speaker_identification(self) -> bool:
        return False

    def add_audio(self, audio: bytes, audio_format: str) -> None:
        if audio:
            self.audios.append({"data": audio})

    def request(self) -> HttpResponse:
        if not self.audios:
            return HttpResponse(
                code=HTTPStatus.UNPROCESSABLE_ENTITY,
                response="no audio provided",
                tokens=TokenCounts(prompt=0, generated=0),
            )
        url = "https://api.elevenlabs.io/v1/speech-to-text"
        headers = {
            "xi-api-key": self.api_key,
        }
        data = {
            "model_id": self.model,
            "diarize": True,
            "temperature": 0,
        }
        self.memory_log.log("--- request begins:")
        request = requests_post(
            url,
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
        result = HttpResponse(
            code=request.status_code,
            response=request.text,
            tokens=TokenCounts(prompt=0, generated=0),
        )
        if result.code == HTTPStatus.OK.value:
            raw_words = request.json()["words"]
            words_list, removed_count = self._filter_hallucinated_words(raw_words)
            if removed_count > 0:
                self.memory_log.log(f"--- filtered {removed_count} hallucinated word(s) ---")

            turns: list[dict] = []
            for words in words_list:
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

            result = HttpResponse(
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
                tokens=TokenCounts(prompt=0, generated=0),
            )

        return result

    @staticmethod
    def _filter_hallucinated_words(words: list[dict]) -> tuple[list[dict], int]:
        """Filter out likely hallucinated words based on timestamp anomalies.

        Words with zero duration (start == end) or clusters of 3+ words sharing
        identical start timestamps are strong signals of ASR hallucination --
        the model generated text without corresponding audio.

        Returns the filtered word list and count of removed words.
        """
        if not words:
            return words, 0

        # Count how many actual words share each start timestamp
        start_counts: dict[float, int] = {}
        for w in words:
            if w["type"] == "word":
                start_counts[w["start"]] = start_counts.get(w["start"], 0) + 1

        filtered = []
        removed = 0
        for w in words:
            if w["type"] == "word":
                is_zero_duration = w["start"] == w["end"]
                is_timestamp_cluster = start_counts.get(w["start"], 0) >= 3

                if is_zero_duration or is_timestamp_cluster:
                    removed += 1
                    continue
            filtered.append(w)

        return filtered, removed
