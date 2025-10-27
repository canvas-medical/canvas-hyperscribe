import json

from canvas_sdk.commands.commands.instruct import InstructCommand
from canvas_sdk.commands.constants import CodeSystems, Coding

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Instruct(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_INSTRUCT

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative") or "n/a"
        if instruct := (data.get("instruct") or {}).get("text"):
            return CodedItem(label=f"{instruct} ({narrative})", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = InstructCommand(comment=instruction.parameters["comment"], note_uuid=self.identification.note_uuid)
        # retrieve existing instructions defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",")
        if concepts := CanvasScience.instructions(expressions):
            # ask the LLM to pick the most relevant instruction
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant direction.",
                "",
            ]
            user_prompt = [
                "Here is the description of a direction instructed by a healthcare provider to a patient:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["comment"],
                "```",
                "Among the following expressions, identify the most relevant one:",
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
                result.coding = Coding(
                    code=str(response[0]["conceptId"]),
                    system=CodeSystems.SNOMED,
                    display=response[0]["term"],
                )
                self.add_code2description(response[0]["conceptId"], "")

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "comment": "",
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
                        "keywords": {
                            "type": "string",
                            "description": "Comma separated single keywords of up to "
                            "5 synonyms to the specific direction",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Directions from the provider, as free text",
                        },
                    },
                    "required": ["keywords", "comment"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Specific or standard direction. "
            "There can be only one direction per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
