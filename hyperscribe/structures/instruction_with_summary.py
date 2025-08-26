from __future__ import annotations

from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_command import InstructionWithCommand


class InstructionWithSummary(InstructionWithCommand):
    def __init__(
        self,
        uuid: str,
        index: int,
        instruction: str,
        information: str,
        is_new: bool,
        is_updated: bool,
        parameters: dict,
        command: _BaseCommand,
        summary: str,
    ):
        super().__init__(uuid, index, instruction, information, is_new, is_updated, parameters, command)
        self.summary = summary

    @classmethod
    def add_explanation(cls, instruction: InstructionWithCommand, summary: str) -> InstructionWithSummary:
        return InstructionWithSummary(
            uuid=instruction.uuid,
            index=instruction.index,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            parameters=instruction.parameters,
            command=instruction.command,
            summary=summary,
        )

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, InstructionWithSummary)
        return super().__eq__(other) and self.summary == other.summary
