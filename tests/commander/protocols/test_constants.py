from commander.protocols.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "HAS_DATABASE_ACCESS": True,
        "OPENAI_CHAT_AUDIO": "gpt-4o-audio-preview",
        "OPENAI_CHAT_TEXT": "gpt-4o",
    }
    assert is_constant(tested, constants)
