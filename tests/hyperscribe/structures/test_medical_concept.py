from hyperscribe.structures.medical_concept import MedicalConcept
from tests.helper import is_namedtuple


def test_class():
    tested = MedicalConcept
    fields = {"concept_id": int, "term": str}
    assert is_namedtuple(tested, fields)
