from __future__ import annotations

from dataclasses import dataclass

from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


@dataclass
class InstructionWithCommand(InstructionWithParameters):
    command: _BaseCommand

    @classmethod
    def add_command(cls, instruction: InstructionWithParameters, command: _BaseCommand) -> InstructionWithCommand:
        return InstructionWithCommand(
            uuid=instruction.uuid,
            index=instruction.index,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            previous_information=instruction.previous_information,
            parameters=instruction.parameters,
            command=command,
        )
