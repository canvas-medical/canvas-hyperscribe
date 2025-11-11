from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from tests.helper import is_dataclass


def test_class():
    tested = InstructionWithCommand
    assert issubclass(tested, InstructionWithParameters)
    fields = {
        "uuid": "str",
        "index": "int",
        "instruction": "str",
        "information": "str",
        "is_new": "bool",
        "is_updated": "bool",
        "previous_information": "str",
        "parameters": "dict",
        "command": "_BaseCommand",
    }
    assert is_dataclass(tested, fields)


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
