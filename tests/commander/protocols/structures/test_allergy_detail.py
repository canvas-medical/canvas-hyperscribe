from commander.protocols.structures.allergy_detail import AllergyDetail
from tests.helper import is_namedtuple


def test_class():
    tested = AllergyDetail
    fields = {
        "concept_id_value": int,
        "concept_id_description": str,
        "concept_type": str,
        "concept_id_type": int,
    }
    assert is_namedtuple(tested, fields)
