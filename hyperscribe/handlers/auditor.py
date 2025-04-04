from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line


class Auditor:
    def identified_transcript(self, audios: list[bytes], transcript: list[Line]) -> bool:
        return True

    def found_instructions(self, transcript: list[Line], instructions: list[Instruction]) -> bool:
        return True

    def computed_parameters(self, sdk_parameters: list[tuple[Instruction, dict]]) -> bool:
        return True

    def computed_commands(self, sdk_parameters: list[tuple[Instruction, dict]], sdk_commands: list[BaseCommand]) -> bool:
        return True
