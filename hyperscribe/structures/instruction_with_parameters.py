from __future__ import annotations

from hyperscribe.structures.instruction import Instruction


class InstructionWithParameters(Instruction):
    def __init__(self, uuid: str, index: int, instruction: str, information: str, is_new: bool, is_updated: bool, audits: list[str],
                 parameters: dict):
        super().__init__(uuid, index, instruction, information, is_new, is_updated, audits)
        self.parameters: dict = parameters

    @classmethod
    def add_parameters(cls, instruction: Instruction, parameters: dict) -> InstructionWithParameters:
        return InstructionWithParameters(
            uuid=instruction.uuid,
            index=instruction.index,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            audits=instruction.audits,
            parameters=parameters,
        )

    def __eq__(self, other: InstructionWithParameters) -> bool:
        return super().__eq__(other) and self.parameters == other.parameters
