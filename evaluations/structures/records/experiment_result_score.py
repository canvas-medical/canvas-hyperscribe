from typing import NamedTuple

from evaluations.structures.graded_criterion import GradedCriterion


class ExperimentResultScore(NamedTuple):
    experiment_result_id: int
    score_id: int = 0
    scoring_result: list[GradedCriterion] = []
    id: int = 0
