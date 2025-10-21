from typing import NamedTuple

from evaluations.structures.graded_criterion import GradedCriterion


class ExperimentResultScore(NamedTuple):
    experiment_result_id: int
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    score_id: int = 0
    scoring_result: list[GradedCriterion] = []
    id: int = 0
