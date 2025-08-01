from evaluations.structures.rubric_criterion import RubricCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = RubricCriterion
    fields = {"criterion": str, "weight": float, "sense": str}

    assert is_namedtuple(tested, fields)
