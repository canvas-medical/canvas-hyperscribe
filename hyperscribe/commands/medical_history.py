import json

from canvas_sdk.commands.commands.medical_history import MedicalHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class MedicalHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_MEDICAL_HISTORY

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comments") or "n/a"
        start_date = (data.get("approximate_start_date") or {}).get("date") or "n/a"
        end_date = (data.get("approximate_end_date") or {}).get("date") or "n/a"
        if text := (data.get("past_medical_history") or {}).get("text"):
            return CodedItem(label=f"{text}: from {start_date} to {end_date} ({comment})", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = MedicalHistoryCommand(
            approximate_start_date=Helper.str2date(instruction.parameters["approximateStartDate"]),
            approximate_end_date=Helper.str2date(instruction.parameters["approximateEndDate"]),
            show_on_condition_list=True,
            comments=instruction.parameters["comments"],
            note_uuid=self.identification.note_uuid,
        )
        # retrieve existing medical history conditions defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",")
        if concepts := CanvasScience.medical_histories(expressions):
            # ask the LLM to pick the most relevant condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the condition of a patient:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["comments"],
                "```",
                "Among the following conditions, identify the most relevant one:",
                "",
                "\n".join(f" * {concept.label} (ICD10: {concept.code})" for concept in concepts),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"ICD10": "the ICD-10 code", "label": "the label"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_condition"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                result.past_medical_history = response[0]["label"]
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "approximateStartDate": None,
            "approximateEndDate": None,
            "comments": "",
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
                            "description": "Comma separated keywords of up to 5 synonyms of the condition",
                        },
                        "approximateStartDate": {
                            "type": ["string", "null"],
                            "description": "Approximate start date in YYYY-MM-DD format",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                        "approximateEndDate": {
                            "type": ["string", "null"],
                            "description": "Approximate end date in YYYY-MM-DD format",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                        "comments": {
                            "type": "string",
                            "description": "Provided description of the patient specific history "
                            "with the condition, as free text",
                        },
                    },
                    "required": ["keywords", "approximateStartDate", "approximateEndDate", "comments"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return "Any past condition. There can be only one condition per instruction, and no instruction in the lack of."

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join(
            [f"{condition.label}" for condition in self.cache.condition_history() + self.cache.current_conditions()]
        ):
            result = f"Only document '{self.class_name()}' for conditions outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return self.settings.commands_policy.is_allowed(self.class_name())
