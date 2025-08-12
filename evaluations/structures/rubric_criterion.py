from __future__ import annotations
from typing import NamedTuple


class RubricCriterion(NamedTuple):
    criterion: str
    weight: float
    sense: str

    def to_json(self) -> dict:
        return {"criterion": self.criterion, "weight": self.weight, "sense": self.sense}

    @classmethod
    def load_from_json(cls, data: list[dict]) -> list[RubricCriterion]:
        return [
            RubricCriterion(criterion=item["criterion"], weight=item["weight"], sense=item["sense"]) for item in data
        ]
