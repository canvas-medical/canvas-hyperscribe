from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import is_namedtuple

def test_class():
    tested = VendorKey
    fields = {
        "vendor": str,
        "api_key": str,
    }
    assert is_namedtuple(tested, fields)
