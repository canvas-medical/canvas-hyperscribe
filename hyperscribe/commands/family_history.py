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
        return Constants.NOTE_SECTION_HISTORY

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
                "Medical context: identify the single most relevant family history condition from the list.",
                "",
            ]
            user_prompt = [
                "Provider data:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                instruction.parameters["note"],
                "```",
                "",
                "Conditions:",
                "\n".join(f" * {concept.term} (conceptId: '{str(concept.concept_id)}')" for concept in concepts),
                "",
                "Return the ONE most relevant condition as JSON in Markdown code block:",
                "```json",
                json.dumps([{"conceptId": "string", "term": "expression"}]),
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
                            "description": "Up to 5 comma-separated condition synonyms",
                        },
                        "relative": {
                            "type": "string",
                            "description": "Family member with condition",
                            "enum": relatives,
                        },
                        "note": {
                            "type": "string",
                            "description": "Condition description",
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
            result = f"Only document '{self.class_name()}' for information outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return True
