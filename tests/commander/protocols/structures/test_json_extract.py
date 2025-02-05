from commander.protocols.structures.json_extract import JsonExtract
from tests.helper import is_namedtuple


def test_class():
    tested = JsonExtract
    fields = {
        "error": str,
        "has_error": bool,
        "content": list,
    }
    assert is_namedtuple(tested, fields)
