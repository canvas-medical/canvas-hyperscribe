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
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_SUBJECTIVE

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
                narrative=self.command_from_json_custom_prompted(instruction.parameters["narrative"], chatter),
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "narrative": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "narrative": {
                            "type": "string",
                            "description": "Description of the patient's symptoms, as free text",
                        },
                    },
                    "required": ["narrative"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Narrative description of the patient's symptoms, observations and related events "
            "e.g. onset, duration, character, timing and severity. "
            "There can be multiple symptoms and descriptors within an instruction, "
            "but only one such instruction in the whole discussion, and no instruction in the lack of. "
            "If an instruction was already found, update the description upon identification."
        )
        if self.custom_prompt():
            result += (
                " For documentation purposes, always include the relevant parts of the transcript for reference, "
                "including any previous sections when merging."
            )
        return result

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
