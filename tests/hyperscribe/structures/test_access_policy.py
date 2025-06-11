from hyperscribe.structures.access_policy import AccessPolicy
from tests.helper import is_namedtuple


def test_class():
    tested = AccessPolicy
    fields = {
        "policy": bool,
        "items": list[str],
    }
    assert is_namedtuple(tested, fields)


def test_is_allowed():
    tested = AccessPolicy(policy=False, items=["Item1", "Item2"])
    tests = [
        ("Item1", False),
        ("Item2", False),
        ("Item3", True),
        ("Item4", True),
        ("Item5", True),
    ]
    for command, expected in tests:
        result = tested.is_allowed(command)
        assert result == expected
    tested = AccessPolicy(policy=True, items=["Item1", "Item2"])
    tests = [
        ("Item1", True),
        ("Item2", True),
        ("Item3", False),
        ("Item4", False),
        ("Item5", False),
    ]
    for command, expected in tests:
        result = tested.is_allowed(command)
        assert result == expected


def test_allow_all():
    tested = AccessPolicy
    result = tested.allow_all()
    expected = AccessPolicy(policy=False, items=[])
    assert result == expected
