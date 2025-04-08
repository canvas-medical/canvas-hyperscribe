from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from tests.helper import is_dataclass


def test_class():
    tested = InstructionWithCommand
    fields = {
        "uuid": "str",
        "instruction": "str",
        "information": "str",
        "is_new": "bool",
        "is_updated": "bool",
        "audits": "list[str]",
        "parameters": "dict",
        "command": "_BaseCommand",
    }
    assert is_dataclass(tested, fields)
    assert issubclass(tested, InstructionWithParameters)


def test_add_parameters():
    tested = InstructionWithCommand
    command = _BaseCommand()
    result = tested.add_command(InstructionWithParameters(
        uuid="theUuid",
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
        parameters={"key": "value"},
    ), command)
    expected = InstructionWithCommand(
        uuid="theUuid",
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        audits=["line1", "line2"],
        parameters={"key": "value"},
        command=command,
    )
    assert result == expected
