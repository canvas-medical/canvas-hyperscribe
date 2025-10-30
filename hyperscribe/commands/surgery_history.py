import json

from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class SurgeryHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_SURGERY_HISTORY

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        on_date = (data.get("approximate_date") or {}).get("date") or "n/a"
        if surgery := (data.get("past_surgical_history") or {}).get("text"):
            code = str((data.get("past_surgical_history") or {}).get("value") or "")
            return CodedItem(label=f"{surgery}: {comment} (on: {on_date})", code=code, uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = PastSurgicalHistoryCommand(
            approximate_date=Helper.str2date(instruction.parameters["approximateDate"]),
            comment=instruction.parameters["comment"],
            note_uuid=self.identification.note_uuid,
        )
        # retrieve existing family history conditions defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",")
        if concepts := CanvasScience.surgical_histories(expressions):
            # ask the LLM to pick the most relevant condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant surgery of a patient out of a list of surgeries.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the surgery of a patient:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["comment"],
                "```",
                "Among the following surgeries, identify the most relevant one:",
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
                result.past_surgical_history = response[0]["term"]

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "approximateDate": None,
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
                            "description": "Comma-separated keywords of up to 5 synonyms of the surgery.",
                        },
                        "approximateDate": {
                            "type": ["string", "null"],
                            "description": "Approximate date of the surgery in YYYY-MM-DD.",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Description of the surgery, as free text.",
                        },
                    },
                    "required": ["keywords", "approximateDate", "comment"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Any past surgery. There can be one and only one surgery per instruction, "
            "and no instruction in the lack of. "
            "Do not create instructions for vague references like 'multiple surgeries' "
            "only create instructions when a specific surgery type is mentioned."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'"{surgery.label}"' for surgery in self.cache.surgery_history()]):
            result = f'"{self.class_name()}" cannot include: {text}.'
        return result

    def is_available(self) -> bool:
        return True
