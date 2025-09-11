from typing import NamedTuple


class GeneratedNote(NamedTuple):
    case_id: int
    cycle_duration: int = 0
    cycle_count: int = 0
    cycle_transcript_overlap: int = 0
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    note_json: list = []
    hyperscribe_version: str = ""
    staged_questionnaires: dict = {}
    transcript2instructions: dict = {}
    instruction2parameters: dict = {}
    parameters2command: dict = {}
    failed: bool = False
    errors: dict = {}
    experiment: bool = False
    id: int = 0
