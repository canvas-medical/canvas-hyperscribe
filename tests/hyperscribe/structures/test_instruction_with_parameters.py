from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from tests.helper import is_dataclass


def test_class():
    tested = InstructionWithParameters
    assert issubclass(tested, Instruction)
    fields = {
        "uuid": "str",
        "index": "int",
        "instruction": "str",
        "information": "str",
        "is_new": "bool",
        "is_updated": "bool",
        "previous_information": "str",
        "parameters": "dict",
    }
    assert is_dataclass(tested, fields)


def test_add_parameters():
    tested = InstructionWithParameters
    result = tested.add_parameters(
        Instruction(
            uuid="theUuid",
            index=3,
            instruction="theInstruction",
            information="theInformation",
            previous_information="thePreviousInformation",
            is_new=True,
            is_updated=True,
        ),
        {"key": "value"},
    )
    expected = InstructionWithParameters(
        uuid="theUuid",
        index=3,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )
    assert result == expected
