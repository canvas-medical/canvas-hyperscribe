import json

from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class FamilyHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_FAMILY_HISTORY

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        label = (data.get("family_history") or {}).get("text")
        relative = (data.get("relative") or {}).get("text")
        if label and relative:
            return CodedItem(label=f"{relative}: {label}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = FamilyHistoryCommand(
            relative=instruction.parameters["relative"],
            note=instruction.parameters["note"],
            note_uuid=self.identification.note_uuid,
        )
        # retrieve existing family history conditions defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",")
        if concepts := CanvasScience.family_histories(expressions):
            # ask the LLM to pick the most relevant condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
                "",
            ]
            user_prompt = [
                "Here is the note provided by the healthcare provider in regards to the condition of a patient:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["note"],
                "```",
                "Among the following conditions, identify the most relevant one:",
                "",
                "\n".join(f" * {concept.term} ({concept.concept_id})" for concept in concepts),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"conceptId": "the concept ID", "term": "the expression"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_concept"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                result.family_history = response[0]["term"]
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "relative": "",
            "note": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        relatives: list[str] = [
            "father",
            "mother",
            "parent",
            "child",
            "brother",
            "sister",
            "sibling",
            "grand-parent",
            "grand-father",
            "grand-mother",
        ]
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
                            "description": "Comma separated keywords of up to 5 synonyms of the condition",
                        },
                        "relative": {
                            "type": "string",
                            "description": "The family member with the condition",
                            "enum": relatives,
                        },
                        "note": {
                            "type": "string",
                            "description": "Description of the condition, as free text",
                        },
                    },
                    "required": ["keywords", "relative", "note"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Any relevant condition of a relative among: "
            "father, mother, parent, child, brother, sister, sibling, grand-parent, grand-father, grand-mother. "
            "There can be only one condition per relative per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f"{history.label}" for history in self.cache.family_history()]):
            result = f'"{self.class_name()}" cannot include: {text}.'
        return result

    def is_available(self) -> bool:
        return True
