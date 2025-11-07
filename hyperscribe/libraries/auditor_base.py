from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


class AuditorBase:
    def identified_transcript(self, audio_bytes: bytes, transcript: list[Line]) -> bool:
        raise NotImplementedError

    def found_instructions(
        self,
        transcript: list[Line],
        initial_instructions: list[Instruction],
        cumulated_instructions: list[Instruction],
    ) -> bool:
        raise NotImplementedError

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        raise NotImplementedError

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        raise NotImplementedError

    def computed_questionnaires(
        self,
        transcript: list[Line],
        initial_instructions: list[Instruction],
        instructions_with_command: list[InstructionWithCommand],
    ) -> bool:
        raise NotImplementedError
