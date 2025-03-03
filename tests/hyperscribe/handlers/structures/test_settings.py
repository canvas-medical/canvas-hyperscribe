from hyperscribe.protocols.structures.settings import Settings
from hyperscribe.protocols.structures.vendor_key import VendorKey
from tests.helper import is_namedtuple


def test_class():
    tested = Settings
    fields = {
        "llm_text": VendorKey,
        "llm_audio": VendorKey,
        "science_host": str,
        "ontologies_host": str,
        "pre_shared_key": str,
        "structured_rfv": bool,
    }
    assert is_namedtuple(tested, fields)
