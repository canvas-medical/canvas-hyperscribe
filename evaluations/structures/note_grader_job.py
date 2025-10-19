from typing import NamedTuple


class NoteGraderJob(NamedTuple):
    job_index: int
    parent_index: int
    rubric_id: int
    generated_note_id: int
    experiment_result_id: int
