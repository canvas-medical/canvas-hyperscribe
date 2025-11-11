from __future__ import annotations

from dataclasses import dataclass

from hyperscribe.structures.instruction import Instruction


@dataclass
class InstructionWithParameters(Instruction):
    parameters: dict

    @classmethod
    def add_parameters(cls, instruction: Instruction, parameters: dict) -> InstructionWithParameters:
        return InstructionWithParameters(
            uuid=instruction.uuid,
            index=instruction.index,
            instruction=instruction.instruction,
            information=instruction.information,
            is_new=instruction.is_new,
            is_updated=instruction.is_updated,
            previous_information=instruction.previous_information,
            parameters=parameters,
        )
