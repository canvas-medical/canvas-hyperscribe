from hyperscribe.structures.token_counts import TokenCounts
from tests.helper import is_dataclass


def test_class():
    tested = TokenCounts
    fields = {
        "prompt": "int",
        "generated": "int",
    }
    assert is_dataclass(tested, fields)


def test_add():
    tested = TokenCounts(178, 37)
    tested.add(TokenCounts(100, 50))
    assert tested.prompt == 278
    assert tested.generated == 87


def test___eq__():
    tested = TokenCounts(178, 37)
    other = TokenCounts(178, 37)
    assert tested == other
    assert tested is not other


def test_to_dict():
    tested = TokenCounts(178, 37)
    result = tested.to_dict()
    expected = {
        "prompt": 178,
        "generated": 37,
    }
    assert result == expected
