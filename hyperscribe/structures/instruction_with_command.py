from __future__ import annotations

from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class InstructionWithCommand(InstructionWithParameters):
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
    ):
        super().__init__(uuid, index, instruction, information, is_new, is_updated, parameters)
        self.command: _BaseCommand = command

    @classmethod
    def add_command(cls, instruction: InstructionWithParameters, command: _BaseCommand) -> InstructionWithCommand:
        result = InstructionWithCommand(
            uuid=instruction.uuid,
            index=instruction.index,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            parameters=instruction.parameters,
            command=command,
        )
        result.set_previous_information(instruction.previous_information)  # need to be able to use typing.Self
        return result

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, InstructionWithCommand)
        return super().__eq__(other) and self.command == other.command
