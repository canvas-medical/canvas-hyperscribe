from hyperscribe.structures.token_counts import TokenCounts


def test_add():
    tested = TokenCounts(178, 37)
    tested.add(TokenCounts(100, 50))
    assert tested.prompt == 278
    assert tested.generated == 87
