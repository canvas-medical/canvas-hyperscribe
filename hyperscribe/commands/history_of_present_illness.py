from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class HistoryOfPresentIllness(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_HISTORY_OF_PRESENT_ILLNESS

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if narrative := data.get("narrative"):
            return CodedItem(label=narrative, code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        return InstructionWithCommand.add_command(
            instruction,
            HistoryOfPresentIllnessCommand(
                narrative=instruction.parameters["narrative"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "narrative": "highlights of the patient's symptoms and surrounding events and observations, as free text",
        }

    def instruction_description(self) -> str:
        return (
            "Highlights of the patient's symptoms and surrounding events and observations. "
            "There can be multiple highlights within an instruction, but only one such instruction in the "
            "whole discussion. "
            "So, if one was already found, simply update it by intelligently merging all key highlights."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
