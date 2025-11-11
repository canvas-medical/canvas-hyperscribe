from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


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


def test___eq__():
    tested = InstructionWithParameters(
        uuid="theUuid",
        index=3,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )
    tests = [
        (
            InstructionWithParameters(
                uuid="theUuid",
                index=3,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
                parameters={"key": "value"},
            ),
            True,
        ),
        (
            InstructionWithParameters(
                uuid="theUuid",
                index=3,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
                parameters={"key": "other"},
            ),
            False,
        ),
    ]
    for other, expected in tests:
        if expected:
            assert tested == other
        else:
            assert tested != other
        assert tested is not other
