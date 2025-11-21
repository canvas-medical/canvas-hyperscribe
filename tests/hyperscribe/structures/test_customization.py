from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.customization import Customization
from hyperscribe.structures.default_tab import DefaultTab
from tests.helper import is_namedtuple


def test_class():
    tested = Customization
    fields = {
        "custom_prompts": list[CustomPrompt],
        "ui_default_tab": DefaultTab,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json():
    tested = Customization
    result = tested.load_from_json(
        {
            "customPrompts": [
                {"active": True, "command": "command1", "prompt": "prompt1"},
                {"active": False, "command": "command2", "prompt": "prompt2"},
                {"active": True, "command": "command3", "prompt": "prompt3"},
            ],
            "uiDefaultTab": "activity",
        }
    )
    expected = Customization(
        ui_default_tab=DefaultTab.ACTIVITY,
        custom_prompts=[
            CustomPrompt(command="command1", prompt="prompt1", active=True),
            CustomPrompt(command="command2", prompt="prompt2", active=False),
            CustomPrompt(command="command3", prompt="prompt3", active=True),
        ],
    )
    assert result == expected


def test_to_dict():
    tested = Customization(
        ui_default_tab=DefaultTab.ACTIVITY,
        custom_prompts=[
            CustomPrompt(command="command1", prompt="prompt1", active=True),
            CustomPrompt(command="command2", prompt="prompt2", active=False),
            CustomPrompt(command="command3", prompt="prompt3", active=True),
        ],
    )
    expected = {
        "customPrompts": [
            {"active": True, "command": "command1", "prompt": "prompt1"},
            {"active": False, "command": "command2", "prompt": "prompt2"},
            {"active": True, "command": "command3", "prompt": "prompt3"},
        ],
        "uiDefaultTab": "activity",
    }
    assert tested.to_dict() == expected
