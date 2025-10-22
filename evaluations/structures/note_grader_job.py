from pathlib import Path
from typing import NamedTuple

from evaluations.structures.records.model import Model


class NoteGraderJob(NamedTuple):
    job_index: int
    parent_index: int
    rubric_id: int
    generated_note_id: int
    model: Model
    model_is_reasoning: bool
    experiment_result_id: int
    cwd_path: Path
