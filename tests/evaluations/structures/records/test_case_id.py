from evaluations.structures.records.case_id import CaseId
from tests.helper import is_namedtuple


def test_class():
    tested = CaseId
    fields = {
        "name": str,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = CaseId()
    assert result.name == ""
    assert result.id == 0
