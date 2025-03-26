from evaluations.structures.evaluation_result import EvaluationResult
from tests.helper import is_namedtuple


def test_class():
    tested = EvaluationResult
    fields = {
        "milliseconds": float,
        "passed": bool,
        "test_file": str,
        "test_name": str,
        "test_case": str,
        "errors": str,
    }
    assert is_namedtuple(tested, fields)
