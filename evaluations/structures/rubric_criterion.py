from __future__ import annotations
from typing import NamedTuple


class RubricCriterion(NamedTuple):
    criterion: str
    weight: float

    def to_json(self) -> dict:
        return {"criterion": self.criterion, "weight": self.weight}

    @classmethod
    def load_from_json(cls, data: list[dict]) -> list[RubricCriterion]:
        return [RubricCriterion(criterion=item["criterion"], weight=item["weight"]) for item in data]
