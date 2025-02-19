from commander.protocols.constants import Constants
from tests.helper import is_constant


def test_constants():
    tested = Constants
    constants = {
        "GOOGLE_CHAT_ALL": "models/gemini-1.5-flash",
        "MAX_WORKERS": 10,
        "OPENAI_CHAT_AUDIO": "gpt-4o-audio-preview",
        "OPENAI_CHAT_TEXT": "gpt-4o",
        "VENDOR_GOOGLE": "Google",
        "VENDOR_OPENAI": "OpenAI",
    }
    assert is_constant(tested, constants)
