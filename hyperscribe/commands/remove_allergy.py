from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class RemoveAllergy(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REMOVE_ALLERGY

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative") or "n/a"
        if allergy := (data.get("allergy") or {}).get("text"):
            return CodedItem(label=f"{allergy}: {narrative}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        allergy_uuid = ""
        if 0 <= (idx := instruction.parameters["allergyIndex"]) < len(current := self.cache.current_allergies()):
            allergy_uuid = current[idx].uuid
            self.add_code2description(current[idx].uuid, current[idx].label)

        return InstructionWithCommand.add_command(
            instruction,
            RemoveAllergyCommand(
                allergy_id=allergy_uuid,
                narrative=instruction.parameters["narrative"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "allergies": "",
            "allergyIndex": -1,
            "narrative": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        allergies = [allergy.label for allergy in self.cache.current_allergies()]
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "allergies": {
                            "type": "string",
                            "description": "The allergy to remove",
                            "enum": allergies,
                        },
                        "allergyIndex": {
                            "type": "integer",
                            "description": "Index of the allergy to remove",
                            "minimum": 0,
                            "maximum": len(allergies) - 1,
                        },
                        "narrative": {
                            "type": "string",
                            "description": "Explanation of why the allergy is removed, as free text",
                        },
                    },
                    "required": ["allergies", "allergyIndex", "narrative"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Remove a previously diagnosed allergy. "
            "There can be only one allergy, with the explanation, to remove per instruction, "
            "and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join([allergy.label for allergy in self.cache.current_allergies()])
        return f"'{self.class_name()}' has to be related to one of the following allergies: {text}."

    def is_available(self) -> bool:
        return bool(self.cache.current_allergies())
