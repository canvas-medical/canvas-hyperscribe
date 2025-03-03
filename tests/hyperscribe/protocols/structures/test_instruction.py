from hyperscribe.protocols.structures.instruction import Instruction
from tests.helper import is_namedtuple


def test_class():
    tested = Instruction
    fields = {
        "uuid": str,
        "instruction": str,
        "information": str,
        "is_new": bool,
        "is_updated": bool,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json():
    tested = Instruction
    result = tested.load_from_json([
        {"uuid": "theUuid1", "instruction": "theInstruction1", "information": "theInformation1", "isNew": False, "isUpdated": True},
        {"uuid": "theUuid2", "instruction": "theInstruction2", "information": "theInformation2", "isNew": True, "isUpdated": False},
        {},
        {"uuid": "theUuid3", "instruction": "theInstruction3", "information": "theInformation3", "isNew": False, "isUpdated": True},
    ])
    expected = [
        Instruction(uuid="theUuid1", instruction="theInstruction1", information="theInformation1", is_new=False, is_updated=True),
        Instruction(uuid="theUuid2", instruction="theInstruction2", information="theInformation2", is_new=True, is_updated=False),
        Instruction(uuid="", instruction="", information="", is_new=True, is_updated=False),
        Instruction(uuid="theUuid3", instruction="theInstruction3", information="theInformation3", is_new=False, is_updated=True),
    ]
    assert result == expected


def test_to_json():
    tested = Instruction(
        uuid="theUuid",
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
    )
    result = tested.to_json()
    expected = {
        "uuid": "theUuid",
        "instruction": "theInstruction",
        "information": "theInformation",
        "isNew": False,
        "isUpdated": False,
    }
    assert expected == result
