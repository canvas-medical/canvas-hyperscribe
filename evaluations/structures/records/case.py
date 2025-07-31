from __future__ import annotations

from typing import NamedTuple

from evaluations.structures.enums.case_status import CaseStatus
from hyperscribe.structures.line import Line


class Case(NamedTuple):
    name: str
    transcript: dict[str, list[Line]] = {}
    limitedChart: dict = {}
    profile: str = ""
    validationStatus: CaseStatus = CaseStatus.GENERATION
    batch_identifier: str = ""
    tags: dict = {}
    id: int = 0

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "transcript": {key: [line.to_json() for line in lines] for key, lines in self.transcript.items()},
            "limited_chart": self.limitedChart,
            "profile": self.profile,
            "validation_status": self.validationStatus.value,
            "batch_identifier": self.batch_identifier,
            "tags": self.tags,
            "id": self.id,
        }

    @classmethod
    def load_record(cls, data: dict) -> Case:
        return Case(
            name=data["name"],
            transcript={key: Line.load_from_json(lines) for key, lines in data["transcript"].items()},
            limited_chart=data["limited_chart"],
            profile=data["profile"],
            validation_status=CaseStatus(data["validation_status"]),
            batch_identifier=data["batch_identifier"],
            tags=data["tags"],
            id=data["id"],
        )
