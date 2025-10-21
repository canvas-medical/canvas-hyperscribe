from typing import NamedTuple


class ExperimentResult(NamedTuple):
    experiment_id: int
    experiment_name: str = ""
    hyperscribe_version: str = ""
    hyperscribe_tags: dict = {}
    case_id: int = 0
    case_name: str = ""
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    cycle_time: int = 0
    cycle_transcript_overlap: int = 0
    failed: bool = False
    errors: dict = {}
    generated_note_id: int = 0
    note_json: list = []
    id: int = 0
