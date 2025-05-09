from canvas_sdk.commands.commands.instruct import InstructCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Immunize(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_IMMUNIZE

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        manufacturer = data.get("manufacturer") or "n/a"
        sig_original = data.get("sig_original") or "n/a"
        if immunization := (data.get("coding") or {}).get("text"):
            return CodedItem(label=f"{immunization}: {sig_original} ({manufacturer})", code="", uuid="")
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        # TODO change to ImmunizeCommand when implemented
        return InstructionWithCommand.add_command(instruction, InstructCommand(
            instruction="Advice to read information",
            comment=f'{instruction.parameters["sig"]} - {instruction.parameters["immunize"]}',
            note_uuid=self.identification.note_uuid,
        ))

    def command_parameters(self) -> dict:
        return {
            "immunize": "medical name of the immunization and its CPT code",
            "sig": "directions, as free text",
        }

    def instruction_description(self) -> str:
        return ("Immunization or vaccine to be administered. "
                "There can be only one immunization per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
