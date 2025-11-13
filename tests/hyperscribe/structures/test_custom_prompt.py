from hyperscribe.structures.custom_prompt import CustomPrompt
from tests.helper import is_namedtuple


def test_class():
    tested = CustomPrompt
    fields = {
        "command": str,
        "prompt": str,
        "active": bool,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json_list():
    tested = CustomPrompt
    #
    result = tested.load_from_json_list([])
    assert result == []
    #
    result = tested.load_from_json_list(
        [
            {"command": "theCommand1", "prompt": "thePrompt1", "active": True},
            {"command": "theCommand2", "prompt": "thePrompt2", "active": False},
            {"command": "theCommand3", "prompt": "thePrompt3"},
        ]
    )
    expected = [
        CustomPrompt(command="theCommand1", prompt="thePrompt1", active=True),
        CustomPrompt(command="theCommand2", prompt="thePrompt2", active=False),
        CustomPrompt(command="theCommand3", prompt="thePrompt3", active=True),
    ]
    assert result == expected
