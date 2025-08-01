from evaluations.structures.graded_criterion import GradedCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = GradedCriterion
    fields = {"id": int, "rationale": str, "satisfaction": int}
    assert is_namedtuple(tested, fields)
