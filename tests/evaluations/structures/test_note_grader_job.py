from evaluations.structures.note_grader_job import NoteGraderJob
from evaluations.structures.records.model import Model
from tests.helper import is_namedtuple


def test_class():
    tested = NoteGraderJob
    fields = {
        "job_index": int,
        "parent_index": int,
        "rubric_id": int,
        "generated_note_id": int,
        "model": Model,
        "model_is_reasoning": bool,
        "experiment_result_id": int,
    }
    assert is_namedtuple(tested, fields)
