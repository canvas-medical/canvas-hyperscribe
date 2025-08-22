from __future__ import annotations

from typing import NamedTuple


class QuestionUsed(NamedTuple):
    dbid: int
    label: str
    used: bool

    def for_llm(self) -> dict:
        return {
            "questionId": self.dbid,
            "question": self.label,
            "usedInTranscript": self.used,
        }

    @classmethod
    def load_from_llm(cls, json_list: list[dict]) -> list[QuestionUsed]:
        return [
            QuestionUsed(
                dbid=data["questionId"],
                label=data["question"],
                used=bool(data["usedInTranscript"]),
            )
            for data in json_list
        ]
