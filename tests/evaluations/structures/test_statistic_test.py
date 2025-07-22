from evaluations.structures.statistic_test import StatisticTest
from tests.helper import is_namedtuple


def test_class():
    tested = StatisticTest
    fields = {"case_name": str, "test_name": str, "passed_count": int}
    assert is_namedtuple(tested, fields)
