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
        return Constants.SECTION_HISTORY

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
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant allergy of a patient out of a list of allergies.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the allergy:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                f"severity: {instruction.parameters['severity']}",
                "",
                instruction.parameters["reaction"],
                "```",
                "",
                "Among the following allergies, identify the most relevant one:",
                "",
                "\n".join(
                    f" * {allergy.concept_id_description} (conceptId: {allergy.concept_id_value})"
                    for allergy in allergies
                ),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"conceptId": "the concept id, as int", "term": "the description"}]),
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
                            "description": "Comma separated keywords of up to 5 distinct synonyms "
                            "of the component related to the allergy or "
                            "'NKA' for No Known Allergy or 'NKDA' for No Known Drug Allergy",
                        },
                        "type": {
                            "type": "string",
                            "description": "Type of allergen",
                            "enum": ["allergy group", "medication", "ingredient"],
                        },
                        "severity": {
                            "type": "string",
                            "description": "Severity of the allergic reaction",
                            "enum": severity_values,
                        },
                        "reaction": {
                            "type": "string",
                            "description": "Description of the reaction, as free text",
                        },
                        "approximateDateOfOnset": {
                            "type": ["string", "null"],
                            "description": "Approximate date of onset in YYYY-MM-DD format",
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
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
