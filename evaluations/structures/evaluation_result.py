from typing import NamedTuple


class EvaluationResult(NamedTuple):
    run_uuid: str
    commit_uuid: str
    milliseconds: float
    passed: bool
    test_file: str
    test_name: str
    case_name: str
    cycle: int
    errors: str
