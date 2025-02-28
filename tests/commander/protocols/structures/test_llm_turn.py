from commander.protocols.structures.llm_turn import LlmTurn
from tests.helper import is_namedtuple


def test_class():
    tested = LlmTurn
    fields = {
        "role": str,
        "text": list[str],
    }
    assert is_namedtuple(tested, fields)
