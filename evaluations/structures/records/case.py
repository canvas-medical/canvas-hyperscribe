from __future__ import annotations

from typing import NamedTuple

from evaluations.structures.enums.case_status import CaseStatus
from hyperscribe.structures.line import Line


class Case(NamedTuple):
    name: str
    transcript: dict[str, list[Line]] = {}
    limited_chart: dict = {}
    profile: str = ""
    validation_status: CaseStatus = CaseStatus.GENERATION
    batch_identifier: str = ""
    tags: dict = {}
    id: int = 0

    @classmethod
    def load_record(cls, data: dict) -> Case:
        return Case(
            name=data["name"],
            transcript={
                key: Line.load_from_json(lines)
                for key, lines in data["transcript"].items()
            },
            limited_chart=data["limited_chart"],
            profile=data["profile"],
            validation_status=CaseStatus(data["validation_status"]),
            batch_identifier=data["batch_identifier"],
            tags=data["tags"],
            id=data["id"],
        )
