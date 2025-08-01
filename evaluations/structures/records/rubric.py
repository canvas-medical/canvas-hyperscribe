from datetime import datetime
from typing import NamedTuple

from evaluations.structures.enums.rubric_validation import RubricValidation


class Rubric(NamedTuple):
    case_id: int
    parent_rubric_id: int | None = None
    validation_timestamp: datetime | None = None
    validation: RubricValidation = RubricValidation.NOT_EVALUATED
    author: str = ""
    rubric: list[dict] = []
    case_provenance_classification: str = ""
    comments: str = ""
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    temperature: float = 0.0
    id: int = 0
