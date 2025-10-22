from pathlib import Path

from evaluations.structures.experiment_job import ExperimentJob
from evaluations.structures.experiment_models import ExperimentModels
from tests.helper import is_namedtuple


def test_class():
    tested = ExperimentJob
    fields = {
        "job_index": int,
        "experiment_id": int,
        "experiment_name": str,
        "case_id": int,
        "case_name": str,
        "models": ExperimentModels,
        "cycle_time": int,
        "cycle_transcript_overlap": int,
        "grade_replications": int,
        "cwd_path": Path,
    }
    assert is_namedtuple(tested, fields)
