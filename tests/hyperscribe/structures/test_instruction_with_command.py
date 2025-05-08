from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


def test_class():
    tested = InstructionWithCommand
    assert issubclass(tested, InstructionWithParameters)


def test_add_parameters():
    tested = InstructionWithCommand
    command = _BaseCommand()
    result = tested.add_command(InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
        parameters={"key": "value"},
    ), command)
    expected = InstructionWithCommand(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
        parameters={"key": "value"},
        command=command,
    )
    assert result == expected
