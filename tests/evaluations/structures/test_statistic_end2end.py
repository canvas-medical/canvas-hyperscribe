from evaluations.structures.statistic_end2end import StatisticEnd2End
from tests.helper import is_namedtuple


def test_class():
    tested = StatisticEnd2End
    fields = {
        "case_name": str,
        "run_count": int,
        "end2end": int,
    }
    assert is_namedtuple(tested, fields)
