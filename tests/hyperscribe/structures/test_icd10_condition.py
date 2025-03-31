from hyperscribe.structures.icd10_condition import Icd10Condition
from tests.helper import is_namedtuple


def test_class():
    tested = Icd10Condition
    fields = {
        "code": str,
        "label": str,
    }
    assert is_namedtuple(tested, fields)
