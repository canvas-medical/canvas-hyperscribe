from typing import NamedTuple


class StatisticEnd2End(NamedTuple):
    case_name: str
    run_count: int
    full_run: int
    end2end: int
