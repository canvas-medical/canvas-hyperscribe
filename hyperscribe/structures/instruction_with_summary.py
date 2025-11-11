from __future__ import annotations

from dataclasses import dataclass

from hyperscribe.structures.instruction_with_command import InstructionWithCommand


@dataclass
class InstructionWithSummary(InstructionWithCommand):
    summary: str

    @classmethod
    def add_explanation(cls, instruction: InstructionWithCommand, summary: str) -> InstructionWithSummary:
        return InstructionWithSummary(
            uuid=instruction.uuid,
            index=instruction.index,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            previous_information=instruction.previous_information,
            parameters=instruction.parameters,
            command=instruction.command,
            summary=summary,
        )
