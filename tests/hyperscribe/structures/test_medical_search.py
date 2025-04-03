from hyperscribe.structures.medication_search import MedicationSearch
from tests.helper import is_namedtuple


def test_class():
    tested = MedicationSearch
    fields = {
        "comment": str,
        "keywords": list[str],
        "brand_names": list[str],
        "related_condition": str,
    }
    assert is_namedtuple(tested, fields)
