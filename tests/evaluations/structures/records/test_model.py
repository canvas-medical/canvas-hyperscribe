from evaluations.structures.records.model import Model
from tests.helper import is_namedtuple


def test_class():
    tested = Model
    fields = {
        "name": str,
        "vendor": str,
        "api_key": str,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = Model()
    assert result.name == ""
    assert result.vendor == ""
    assert result.api_key == ""
    assert result.id == 0
