from typing import NamedTuple

from hyperscribe.structures.token_counts import TokenCounts


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
    token_counts: TokenCounts = TokenCounts(prompt=0, generated=0)
    id: int = 0
