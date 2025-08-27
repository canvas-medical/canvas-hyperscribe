from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


def test_class():
    tested = InstructionWithParameters
    assert issubclass(tested, Instruction)


def test_add_parameters():
    tested = InstructionWithParameters
    result = tested.add_parameters(
        Instruction(
            uuid="theUuid",
            index=3,
            instruction="theInstruction",
            information="theInformation",
            is_new=True,
            is_updated=True,
        ).set_previous_information("thePreviousInformation"),
        {"key": "value"},
    )
    expected = InstructionWithParameters(
        uuid="theUuid",
        index=3,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        parameters={"key": "value"},
    )
    expected.previous_information = "thePreviousInformation"
    assert result == expected
