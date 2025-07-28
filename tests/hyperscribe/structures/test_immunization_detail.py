from hyperscribe.structures.immunization_detail import ImmunizationDetail
from tests.helper import is_namedtuple


def test_class():
    tested = ImmunizationDetail
    fields = {
        "label": str,
        "code_cpt": str,
        "code_cvx": str,
        "cvx_description": str,
    }
    assert is_namedtuple(tested, fields)
