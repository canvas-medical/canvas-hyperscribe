from hyperscribe.structures.custom_prompt import CustomPrompt
from tests.helper import is_namedtuple


def test_class():
    tested = CustomPrompt
    fields = {"command": str, "prompt": str}
    assert is_namedtuple(tested, fields)


def test_load_from_json_list():
    tested = CustomPrompt
    #
    result = tested.load_from_json_list([])
    assert result == []
    #
    result = tested.load_from_json_list(
        [
            {"command": "theCommand1", "prompt": "thePrompt1"},
            {"command": "theCommand2", "prompt": "thePrompt2"},
            {"command": "theCommand3", "prompt": "thePrompt3"},
        ]
    )
    expected = [
        CustomPrompt(command="theCommand1", prompt="thePrompt1"),
        CustomPrompt(command="theCommand2", prompt="thePrompt2"),
        CustomPrompt(command="theCommand3", prompt="thePrompt3"),
    ]
    assert result == expected
