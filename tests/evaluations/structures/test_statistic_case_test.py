from evaluations.structures.statistic_case_test import StatisticCaseTest
from tests.helper import is_dataclass


def test_class():
    tested = StatisticCaseTest
    fields = {
        "case_name": str,
        "run_count": int,
        "audio2transcript": int,
        "transcript2instructions": int,
        "instruction2parameters": int,
        "parameters2command": int,
        "end2end": int,
    }
    assert is_dataclass(tested, fields)
