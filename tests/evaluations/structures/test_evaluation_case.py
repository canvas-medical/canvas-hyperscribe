from evaluations.structures.evaluation_case import EvaluationCase
from tests.helper import is_namedtuple


def test_class():
    tested = EvaluationCase
    fields = {
        "environment": str,
        "patient_uuid": str,
        "limited_cache": dict,
        "case_type": str,
        "case_group": str,
        "case_name": str,
        "description": str,
    }
    assert is_namedtuple(tested, fields)
