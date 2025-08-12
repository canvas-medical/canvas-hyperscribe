from __future__ import annotations
from typing import NamedTuple


class GradedCriterion(NamedTuple):
    id: int
    rationale: str
    satisfaction: int
    score: float

    def to_json(self) -> dict:
        return {"id": self.id, "rationale": self.rationale, "satisfaction": self.satisfaction, "score": self.score}

    @classmethod
    def load_from_json(cls, data: list[dict]) -> list[GradedCriterion]:
        # Convert into list graded criterion and setting placeholder score. -0.000 isn't possible by score calc.
        return [
            GradedCriterion(id=item["id"], rationale=item["rationale"], satisfaction=item["satisfaction"], score=-0.000)
            for item in data
        ]
