from typing import NamedTuple


class EvaluationResult(NamedTuple):
    milliseconds: float
    passed: bool
    test_file: str
    test_name: str
    test_case: str
    errors: str
