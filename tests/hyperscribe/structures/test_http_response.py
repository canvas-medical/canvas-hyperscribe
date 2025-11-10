from hyperscribe.structures.http_response import HttpResponse
from tests.helper import is_namedtuple

from hyperscribe.structures.token_counts import TokenCounts


def test_class():
    tested = HttpResponse
    fields = {
        "code": int,
        "response": str,
        "tokens": TokenCounts,
    }
    assert is_namedtuple(tested, fields)
