from typing import NamedTuple


class Score(NamedTuple):
    rubric_id: int
    generated_note_id: int
    scoring_result: dict = {}
    overall_score: float = 0.0
    comments: str = ""
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    temperature: float = 0.0
    id: int = 0
