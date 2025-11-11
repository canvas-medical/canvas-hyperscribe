from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


def test_add_command():
    tested = InstructionWithCommand
    command = _BaseCommand()
    result = tested.add_command(
        InstructionWithParameters(
            uuid="theUuid",
            index=7,
            instruction="theInstruction",
            information="theInformation",
            is_new=True,
            is_updated=True,
            previous_information="thePreviousInformation",
            parameters={"key": "value"},
        ),
        command,
    )
    expected = InstructionWithCommand(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
        command=command,
    )
    assert result == expected


def test___eq__():
    command = _BaseCommand()
    tested = InstructionWithCommand(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
        command=command,
    )
    tests = [
        (
            InstructionWithCommand(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
                parameters={"key": "value"},
                command=command,
            ),
            True,
        ),
    ]
    for other, expected in tests:
        if expected:
            assert tested == other
        else:
            assert tested != other
        assert tested is not other
