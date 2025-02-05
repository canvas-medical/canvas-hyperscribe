from commander.protocols.structures.http_response import HttpResponse
from tests.helper import is_namedtuple


def test_class():
    tested = HttpResponse
    fields = {
        "code": int,
        "response": str,
    }
    assert is_namedtuple(tested, fields)
