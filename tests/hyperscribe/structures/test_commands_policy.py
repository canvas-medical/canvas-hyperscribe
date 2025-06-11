from hyperscribe.structures.commands_policy import CommandsPolicy
from tests.helper import is_namedtuple


def test_class():
    tested = CommandsPolicy
    fields = {
        "policy": bool,
        "commands": list[str],
    }
    assert is_namedtuple(tested, fields)


def test_is_allowed():
    tested = CommandsPolicy(policy=False, commands=["Command1", "Command2"])
    tests = [
        ("Command1", False),
        ("Command2", False),
        ("Command3", True),
        ("Command4", True),
        ("Command5", True),
    ]
    for command, expected in tests:
        result = tested.is_allowed(command)
        assert result == expected
    tested = CommandsPolicy(policy=True, commands=["Command1", "Command2"])
    tests = [
        ("Command1", True),
        ("Command2", True),
        ("Command3", False),
        ("Command4", False),
        ("Command5", False),
    ]
    for command, expected in tests:
        result = tested.is_allowed(command)
        assert result == expected


def test_allow_all():
    tested = CommandsPolicy
    result = tested.allow_all()
    expected = CommandsPolicy(policy=False, commands=[])
    assert result == expected
