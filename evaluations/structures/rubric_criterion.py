from typing import NamedTuple


class RubricCriterion(NamedTuple):
    criterion: str
    weight: float
    sense: str
