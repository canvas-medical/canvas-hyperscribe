import json

from canvas_sdk.commands.commands.allergy import AllergyCommand, Allergen, AllergenType

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Allergy(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ALLERGY

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (allergy := data.get("allergy", {})) and "text" in allergy and "value" in allergy:
            return CodedItem(label=allergy["text"], code=str(allergy["value"]), uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        concept_types = [AllergenType(1)]  # <-- always include the Allergy Group
        if instruction.parameters["type"] == "medication":
            concept_types.append(AllergenType(2))
        elif instruction.parameters["type"] == "ingredient":
            concept_types.append(AllergenType(6))

        # retrieve existing allergies defined in Canvas Ontologies
        expressions = instruction.parameters["keywords"].split(",")
        allergies = CanvasScience.search_allergy(expressions, concept_types)
        result = AllergyCommand(
            severity=Helper.enum_or_none(instruction.parameters["severity"], AllergyCommand.Severity),
            narrative=instruction.parameters["reaction"],
            approximate_date=Helper.str2date(instruction.parameters["approximateDateOfOnset"]),
            note_uuid=self.identification.note_uuid,
        )
        if allergies:
            # retrieve the correct allergy
            system_prompt = [
                "Medical context: identify the single most relevant allergy from the list.",
                "",
            ]
            user_prompt = [
                "Provider data:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                f"severity: {instruction.parameters['severity']}",
                instruction.parameters["reaction"],
                "```",
                "",
                "Allergies:",
                "\n".join(
                    f" * {allergy.concept_id_description} (conceptId: '{str(allergy.concept_id_value)}')"
                    for allergy in allergies
                ),
                "",
                "Return the ONE most relevant allergy as JSON in Markdown code block:",
                "```json",
                json.dumps([{"conceptId": "string", "term": "description"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_concept"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                concept_id = int(response[0]["conceptId"])
                allergy = [allergy for allergy in allergies if allergy.concept_id_value == concept_id][0]
                result.allergy = Allergen(concept_id=concept_id, concept_type=AllergenType(allergy.concept_id_type))
                self.add_code2description(str(allergy.concept_id_value), allergy.concept_id_description)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "type": "",
            "severity": "",
            "reaction": "",
            "approximateDateOfOnset": None,
        }

    def command_parameters_schemas(self) -> list[dict]:
        severity_values: list[str] = [status.value for status in AllergyCommand.Severity]
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "string",
                            "description": "Up to 5 comma-separated allergy component synonyms, "
                            "or 'NKA' (No Known Allergy) or 'NKDA' (No Known Drug Allergy)",
                        },
                        "type": {
                            "type": "string",
                            "description": "Allergen type",
                            "enum": ["allergy group", "medication", "ingredient"],
                        },
                        "severity": {
                            "type": "string",
                            "description": "Allergic reaction severity",
                            "enum": severity_values,
                        },
                        "reaction": {
                            "type": "string",
                            "description": "Reaction description",
                        },
                        "approximateDateOfOnset": {
                            "type": ["string", "null"],
                            "description": "Onset date YYYY-MM-DD",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                    },
                    "required": ["keywords", "type", "severity", "reaction", "approximateDateOfOnset"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Any diagnosed allergy, one instruction per allergy. "
            "There can be only one allergy per instruction, and no instruction in the lack of. "
            "But, if it is explicitly said that the patient has no known allergy, add an instruction mentioning it."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([allergy.label for allergy in self.cache.current_allergies()]):
            result = f"Only document '{self.class_name()}' for allergies outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return True
