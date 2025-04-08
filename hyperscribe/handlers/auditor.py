from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


class Auditor:
    def identified_transcript(self, audios: list[bytes], transcript: list[Line]) -> bool:
        return True

    def found_instructions(self, transcript: list[Line], instructions: list[Instruction]) -> bool:
        return True

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        return True

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        return True
