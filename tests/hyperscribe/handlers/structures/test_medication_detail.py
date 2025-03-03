from hyperscribe.protocols.structures.medication_detail import MedicationDetail
from hyperscribe.protocols.structures.medication_detail_quantity import MedicationDetailQuantity
from tests.helper import is_namedtuple


def test_class():
    tested = MedicationDetail
    fields = {
        "fdb_code": str,
        "description": str,
        "quantities": list[MedicationDetailQuantity],
    }
    assert is_namedtuple(tested, fields)
