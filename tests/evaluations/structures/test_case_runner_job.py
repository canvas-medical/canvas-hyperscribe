from evaluations.structures.case_runner_job import CaseRunnerJob
from tests.helper import is_namedtuple


def test_class():
    tested = CaseRunnerJob
    fields = {
        "case_name": str,
        "experiment_result_id": int,
    }
    assert is_namedtuple(tested, fields)
