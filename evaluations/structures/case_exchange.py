from __future__ import annotations

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class CaseExchange:
    speaker: str
    text: str
    chunk: int

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Self]:
        return cls.load_from_json_default(json_list, 1)

    @classmethod
    def load_from_json_default(cls, json_list: list, default_chunk: int) -> list[Self]:
        return [
            cls(
                speaker=json_object["speaker"],
                text=json_object["text"],
                chunk=json_object.get("chunk", default_chunk),
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "chunk": self.chunk,
        }
