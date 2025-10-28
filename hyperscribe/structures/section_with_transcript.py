from __future__ import annotations

from typing import NamedTuple

from hyperscribe.structures.line import Line


class SectionWithTranscript(NamedTuple):
    section: str
    transcript: list[Line]

    @classmethod
    def load_from(cls, data: list) -> list[SectionWithTranscript]:
        return [
            SectionWithTranscript(section=section["section"], transcript=Line.load_from_json(section["transcript"]))
            for section in data
        ]
