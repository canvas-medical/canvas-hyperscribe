from hyperscribe.handlers.structures.coded_item import CodedItem
from tests.helper import is_namedtuple


def test_class():
    tested = CodedItem
    fields = {
        "uuid": str,
        "label": str,
        "code": str,
    }
    assert is_namedtuple(tested, fields)
