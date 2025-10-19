from evaluations.structures.experiment_job import ExperimentJob
from tests.helper import is_namedtuple


def test_class():
    tested = ExperimentJob
    fields = {
        "job_index": int,
        "experiment_id": int,
        "experiment_name": str,
        "case_id": int,
        "case_name": str,
        "model_id": int,
        "model_vendor": str,
        "model_name": str,
        "model_api_key": str,
        "cycle_time": int,
        "cycle_transcript_overlap": int,
        "grade_replications": int,
    }
    assert is_namedtuple(tested, fields)
