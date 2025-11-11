from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_summary import InstructionWithSummary


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


def test___eq__():
    command = _BaseCommand()
    tested = InstructionWithSummary(
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
    tests = [
        (
            InstructionWithSummary(
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
            ),
            True,
        ),
        (
            InstructionWithSummary(
                uuid="theUuid",
                index=7,
                instruction="theInstruction",
                information="theInformation",
                is_new=True,
                is_updated=True,
                previous_information="thePreviousInformation",
                parameters={"key": "value"},
                command=command,
                summary="other summary",
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
