from typing import NamedTuple
from evaluations.structures.graded_criterion import GradedCriterion


class Score(NamedTuple):
    rubric_id: int
    generated_note_id: int
    scoring_result: list[GradedCriterion] = []
    overall_score: float = 0.0
    comments: str = ""
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    temperature: float = 0.0
    experiment: bool = False
    id: int = 0
