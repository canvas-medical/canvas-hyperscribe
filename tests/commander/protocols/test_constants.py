from commander.protocols.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "OPENAI_CHAT_AUDIO": "gpt-4o-audio-preview",
        "OPENAI_CHAT_TEXT": "gpt-4o",
        "MAX_WORKERS": 10,
    }
    assert is_constant(tested, constants)
