from __future__ import annotations

from typing import NamedTuple

from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.chart import Chart
from hyperscribe.structures.line import Line


class Case(NamedTuple):
    name: str
    transcript: dict[str, list[Line]] = {}
    limited_chart: Chart = Chart(
        demographic_str="",
        condition_history=[],
        current_allergies=[],
        current_conditions=[],
        current_medications=[],
        current_goals=[],
        family_history=[],
        surgery_history=[],
    )
    profile: str = ""
    validation_status: CaseStatus = CaseStatus.GENERATION
    batch_identifier: str = ""
    tags: dict = {}
    id: int = 0

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "transcript": {key: [line.to_json() for line in lines] for key, lines in self.transcript.items()},
            "limitedChart": self.limited_chart.to_json(),
            "profile": self.profile,
            "validationStatus": self.validation_status.value,
            "batchIdentifier": self.batch_identifier,
            "tags": self.tags,
            "id": self.id,
        }

    @classmethod
    def load_record(cls, data: dict) -> Case:
        return Case(
            name=data["name"],
            transcript={key: Line.load_from_json(lines) for key, lines in data["transcript"].items()},
            limited_chart=Chart.load_from_json(data["limited_chart"]),
            profile=data["profile"],
            validation_status=CaseStatus(data["validation_status"]),
            batch_identifier=data["batch_identifier"],
            tags=data["tags"],
            id=data["id"],
        )
