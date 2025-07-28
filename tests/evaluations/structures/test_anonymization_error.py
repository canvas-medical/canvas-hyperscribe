from evaluations.structures.anonymization_error import AnonymizationError
from tests.helper import is_namedtuple


def test_class():
    tested = AnonymizationError
    fields = {"has_errors": bool, "errors": list[str]}
    assert is_namedtuple(tested, fields)
