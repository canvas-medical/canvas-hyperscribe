from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from evaluations.structures.case_exchange import CaseExchange


@dataclass(frozen=True)
class TopicalExchange(CaseExchange):
    topic: int

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Self]:
        return [
            cls(
                speaker=json_object["speaker"],
                text=json_object["text"],
                chunk=json_object["chunk"],
                topic=json_object["topic"],
                start=json_object["start"],
                end=json_object["end"],
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "chunk": self.chunk,
            "topic": self.topic,
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def case_exchange_from(cls, exchange: list[TopicalExchange]) -> list[CaseExchange]:
        return [
            CaseExchange(
                speaker=line.speaker,
                text=line.text,
                chunk=line.chunk,
                start=line.start,
                end=line.end,
            )
            for line in exchange
        ]
