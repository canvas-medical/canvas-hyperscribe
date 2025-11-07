import json

from hyperscribe.libraries.auditor_base import AuditorBase
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class AuditorLive(AuditorBase):
    def __init__(
        self,
        cycle: int,
        settings: Settings,
        s3_credentials: AwsS3Credentials,
        identification: IdentificationParameters,
    ) -> None:
        self.cycle = max(0, cycle)
        self.settings = settings
        self.s3_credentials = s3_credentials
        self.identification = identification

    def identified_transcript(self, audio_bytes: bytes, transcript: list[Line]) -> bool:
        client_s3 = AwsS3(self.s3_credentials)
        if client_s3.is_ready():
            store_path = (
                f"hyperscribe-{self.identification.canvas_instance}/"
                "transcripts/"
                f"{self.identification.note_uuid}/"
                f"transcript_{self.cycle:02d}.log"
            )
            client_s3.upload_text_to_s3(store_path, json.dumps([line.to_json() for line in transcript], indent=2))
        return True

    def found_instructions(
        self,
        transcript: list[Line],
        initial_instructions: list[Instruction],
        cumulated_instructions: list[Instruction],
    ) -> bool:
        return True

    def computed_parameters(self, instructions: list[InstructionWithParameters]) -> bool:
        return True

    def computed_commands(self, instructions: list[InstructionWithCommand]) -> bool:
        return True

    def computed_questionnaires(
        self,
        transcript: list[Line],
        initial_instructions: list[Instruction],
        instructions_with_command: list[InstructionWithCommand],
    ) -> bool:
        return True
