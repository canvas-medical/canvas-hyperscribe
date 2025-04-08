from __future__ import annotations

from dataclasses import dataclass

from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


@dataclass(frozen=True)
class InstructionWithCommand(InstructionWithParameters):
    command: _BaseCommand

    @classmethod
    def add_command(cls, instruction: InstructionWithParameters, command: _BaseCommand) -> InstructionWithCommand:
        return InstructionWithCommand(
            uuid=instruction.uuid,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            audits=instruction.audits,
            parameters=instruction.parameters,
            command=command
        )
