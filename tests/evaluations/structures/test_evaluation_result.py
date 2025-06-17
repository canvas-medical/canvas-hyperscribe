from evaluations.structures.evaluation_result import EvaluationResult
from tests.helper import is_namedtuple


def test_class():
    tested = EvaluationResult
    fields = {
        "run_uuid": str,
        "commit_uuid": str,
        "milliseconds": float,
        "passed": bool,
        "test_file": str,
        "test_name": str,
        "case_name": str,
        "cycle": int,
        "errors": str,
    }
    assert is_namedtuple(tested, fields)
