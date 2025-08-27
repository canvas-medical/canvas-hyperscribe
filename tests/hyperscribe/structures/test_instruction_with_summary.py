from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_summary import InstructionWithSummary


def test_class():
    tested = InstructionWithSummary
    assert issubclass(tested, InstructionWithCommand)


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
            parameters={"key": "value"},
            command=command,
        ).set_previous_information("thePreviousInformation"),
        "the summary",
    )
    expected = InstructionWithSummary(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
        parameters={"key": "value"},
        command=command,
        summary="the summary",
    )
    expected.previous_information = "thePreviousInformation"
    assert result == expected
