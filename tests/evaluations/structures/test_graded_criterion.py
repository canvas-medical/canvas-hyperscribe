from evaluations.structures.graded_criterion import GradedCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = GradedCriterion
    fields = {
        "id": str,
        "rationale": str,
        "satisfaction": str}
    assert is_namedtuple(tested, fields)