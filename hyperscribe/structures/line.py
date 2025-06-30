from __future__ import annotations

from typing import NamedTuple


class Line(NamedTuple):
    speaker: str
    text: str

    @classmethod
    def load_from_json(cls, json_list: list) -> list[Line]:
        return [
            Line(
                speaker=json_object.get("speaker", ""),
                text=json_object.get("text", ""),
            )
            for json_object in json_list
        ]

    def to_json(self) -> dict:
        return {
            "speaker": self.speaker,
            "text": self.text,
        }

    @classmethod
    def tail_of(cls, exchange: list[Line]) -> list[Line]:
        result: list[Line] = []
        max_words = 100
        for line in exchange[::-1]:
            words_count = sum([len(l.text.split()) for l in result])
            next_count = len(line.text.split())
            if words_count + next_count < max_words:
                result.insert(0, line)
            else:
                result.insert(0, Line(
                    speaker=line.speaker,
                    text=" ".join(line.text.split()[-1 * (max_words - words_count):]),
                ))
                break
        return result
