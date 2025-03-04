from hyperscribe.handlers.structures.medication_detail_quantity import MedicationDetailQuantity
from tests.helper import is_namedtuple


def test_class():
    tested = MedicationDetailQuantity
    fields = {
        "quantity": str,
        "representative_ndc": str,
        "ncpdp_quantity_qualifier_code": str,
        "ncpdp_quantity_qualifier_description": str,
    }
    assert is_namedtuple(tested, fields)
