from hyperscribe.structures.http_response import HttpResponse
from hyperscribe.structures.token_counts import TokenCounts
from tests.helper import is_namedtuple


def test_class():
    tested = HttpResponse
    fields = {
        "code": int,
        "response": str,
        "tokens": TokenCounts,
    }
    assert is_namedtuple(tested, fields)
