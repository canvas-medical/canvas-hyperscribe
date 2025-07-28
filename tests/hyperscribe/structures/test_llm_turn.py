from hyperscribe.structures.llm_turn import LlmTurn
from tests.helper import is_namedtuple


def test_class():
    tested = LlmTurn
    fields = {"role": str, "text": list[str]}
    assert is_namedtuple(tested, fields)


def test_to_dict():
    tested = LlmTurn(role="theRole", text=["text1", "text2"])
    expected = {"role": "theRole", "text": ["text1", "text2"]}
    assert tested.to_dict() == expected


def test_load_from_json():
    tested = LlmTurn
    # empty list
    result = tested.load_from_json([])
    assert result == []
    #
    result = tested.load_from_json(
        [
            {"role": "role1", "text": ["text1"]},
            {"role": "role2", "text": ["text2"]},
            {"role": "role3", "text": ["text3"]},
        ],
    )
    expected = [
        LlmTurn(role="role1", text=["text1"]),
        LlmTurn(role="role2", text=["text2"]),
        LlmTurn(role="role3", text=["text3"]),
    ]
    assert result == expected
