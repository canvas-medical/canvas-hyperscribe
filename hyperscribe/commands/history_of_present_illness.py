from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class HistoryOfPresentIllness(Base):
    @classmethod
    def command_type(cls) -> str:
        return "HistoryOfPresentIllnessCommand"

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
        # Get the narrative content with custom prompt processing
        narrative = self.command_from_json_custom_prompted(instruction.parameters["narrative"], chatter)

        # Fill template content if a template framework exists, or enhance with {add:} instructions
        narrative = self.fill_template_content(narrative, "narrative", instruction, chatter)

        return InstructionWithCommand.add_command(
            instruction,
            HistoryOfPresentIllnessCommand(
                narrative=narrative,
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
                            "description": (
                                "History of present illness narrative in standard "
                                "SOAP note style. "
                                "Write from the patient's perspective using "
                                "clinical charting language. "
                                "Do NOT narrate what the clinician did "
                                "(e.g. avoid 'The clinician discussed', "
                                "'The provider reviewed'). "
                                "Structure with the following sections, "
                                "each on its own line:\n"
                                "1. Opening line: the patient's name, age, "
                                "and type of visit, along with known "
                                "conditions and problems.\n"
                                "2. Symptoms: a summary of the patient's "
                                "reported symptoms, including aggravating "
                                "and alleviating factors.\n"
                                "3. Visit recap: a brief recap of the visit "
                                "(e.g. 'During today's visit...').\n"
                                "4. Conditions evaluated: a list of the "
                                "conditions and problems that were evaluated.\n"
                                "5. Patient discussion: key points discussed "
                                "with the patient, including patient concerns, "
                                "education provided, and patient understanding "
                                "or agreement with the plan.\n"
                                "Separate each section with a blank line "
                                "for readability."
                            ),
                        },
                    },
                    "required": ["narrative"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        result = (
            "History of present illness narrative covering: "
            "the patient's name, age, and visit type with known conditions; "
            "a summary of reported symptoms including what makes them better or worse; "
            "a recap of the visit (e.g. 'During today's visit...'); "
            "the conditions and problems that were evaluated; "
            "and key points discussed with the patient. "
            "There can be multiple highlights within an instruction, but only one such instruction in the "
            "whole discussion. "
            "So, if one was already found, simply update it by intelligently merging all key highlights."
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
        return self.can_edit_field("narrative")
