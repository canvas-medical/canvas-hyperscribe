from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_summary import InstructionWithSummary
from tests.helper import is_dataclass


def test_class():
    tested = InstructionWithSummary
    assert issubclass(tested, InstructionWithCommand)
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
        "summary": "str",
    }
    assert is_dataclass(tested, fields)


def test_add_explanation():
    tested = InstructionWithSummary
    command = _BaseCommand()
    result = tested.add_explanation(
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
        "the summary",
    )
    expected = InstructionWithSummary(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
        command=command,
        summary="the summary",
    )
    assert result == expected
