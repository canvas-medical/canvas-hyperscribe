from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


def test_class():
    tested = InstructionWithParameters
    assert issubclass(tested, Instruction)


def test_add_parameters():
    tested = InstructionWithParameters
    result = tested.add_parameters(Instruction(
        uuid="theUuid",
        index=3,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
    ), {"key": "value"})
    expected = InstructionWithParameters(
        uuid="theUuid",
        index=3,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
        parameters={"key": "value"},
    )
    assert result == expected
