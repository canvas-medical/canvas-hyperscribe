from hyperscribe.structures.identification_parameters import IdentificationParameters
from tests.helper import is_namedtuple


def test_class():
    tested = IdentificationParameters
    fields = {
        "patient_uuid": str,
        "note_uuid": str,
        "provider_uuid": str,
        "canvas_instance": str,
    }
    assert is_namedtuple(tested, fields)
