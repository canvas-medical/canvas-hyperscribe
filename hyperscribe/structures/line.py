from __future__ import annotations

from typing import NamedTuple


class Line(NamedTuple):
    speaker: str
    text: str
    start: float = 0.0
    end: float = 0.0

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Line]:
        return [
            Line(
                speaker=json_object.get("speaker", ""),
                text=json_object.get("text", ""),
                start=json_object.get("start") or 0.0,
                end=json_object.get("end") or 0.0,
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
            "start": self.start,
            "end": self.end,
        }

    @classmethod
    def tail_of(cls, exchange: list[Line], max_words: int) -> list[Line]:
        result: list[Line] = []
        for line in exchange[::-1]:
            words_count = sum([len(l.text.split()) for l in result])
            next_count = len(line.text.split())
            if words_count + next_count < max_words:
                result.insert(0, line)
            else:
                result.insert(
                    0,
                    Line(
                        speaker=line.speaker,
                        text=" ".join(line.text.split()[-1 * (max_words - words_count) :]),
                        start=line.start,  # <-- not accurate but good enough
                        end=line.end,
                    ),
                )
                break
        return result
