import json

from canvas_sdk.commands.commands.update_diagnosis import UpdateDiagnosisCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class UpdateDiagnose(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_DIAGNOSE

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_ASSESSMENT

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if condition := (data.get("condition") or {}).get("text"):
            new_condition = (data.get("new_condition") or {}).get("text") or "n/a"
            narrative = data.get("narrative") or "n/a"
            return CodedItem(label=f"{condition} to {new_condition}: {narrative}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        # Get field values with template permission checks
        background: str | None = None
        if self.can_edit_field("background"):
            background = instruction.parameters["rationale"]
            background = self.enhance_with_template_instructions(background, "background", instruction, chatter)

        narrative: str | None = None
        if self.can_edit_field("narrative"):
            narrative = instruction.parameters["assessment"]
            narrative = self.enhance_with_template_instructions(narrative, "narrative", instruction, chatter)

        # If neither field can be edited, skip this command
        if background is None and narrative is None:
            return None

        result = UpdateDiagnosisCommand(
            background=background or "",
            narrative=narrative or "",
            note_uuid=self.identification.note_uuid,
        )
        if (
            0
            <= (idx := instruction.parameters["previousConditionIndex"])
            < len(current := self.cache.current_conditions())
        ):
            result.condition_code = Helper.icd10_strip_dot(current[idx].code)
            self.add_code2description(current[idx].uuid, current[idx].label)

        # retrieve existing conditions defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",") + instruction.parameters["ICD10"].split(",")
        if conditions := CanvasScience.search_conditions(expressions):
            # retrieve the correct condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition diagnosed for a patient "
                "out of a list of conditions.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the diagnosis:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["rationale"],
                "",
                instruction.parameters["assessment"],
                "```",
                "",
                "Sort the following conditions from most relevant to least, and return the first one:",
                "",
                "\n".join(
                    f" * {condition.label} (ICD-10: {Helper.icd10_add_dot(condition.code)})" for condition in conditions
                ),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"ICD10": "the ICD-10 code", "label": "the label"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_condition"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                diagnosis = response[0]
                result.new_condition_code = Helper.icd10_strip_dot(diagnosis["ICD10"])
                self.add_code2description(diagnosis["ICD10"], diagnosis["label"])

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "keywords": "",
            "ICD10": "",
            "previousCondition": "",
            "previousConditionIndex": -1,
            "rationale": "",
            "assessment": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        conditions = [condition.label for condition in self.cache.current_conditions()]
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
                            "description": "Comma separated keywords of up to 5 synonyms of "
                            "the new diagnosed condition",
                        },
                        "ICD10": {
                            "type": "string",
                            "description": "Comma separated keywords of up to 5 ICD-10 codes of "
                            "the new diagnosed condition",
                        },
                        "previousCondition": {
                            "type": "string",
                            "description": "The previous condition to be updated",
                            "enum": conditions,
                        },
                        "previousConditionIndex": {
                            "type": "integer",
                            "description": "Index of the previous Condition",
                            "minimum": 0,
                            "maximum": len(conditions) - 1,
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Rationale about the current assessment, as free text",
                        },
                        "assessment": {
                            "type": "string",
                            "description": "Today's assessment of the new condition, as free text",
                        },
                    },
                    "required": [
                        "keywords",
                        "ICD10",
                        "previousCondition",
                        "previousConditionIndex",
                        "rationale",
                        "assessment",
                    ],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        text = ", ".join([f"{condition.label}" for condition in self.cache.current_conditions()])
        return (
            f"Change of a medical condition ({text}) identified by the provider, "
            f"including rationale, current assessment. "
            "There is one instruction per condition change, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join(
            [f"{condition.label} (ICD-10: {condition.code})" for condition in self.cache.current_conditions()],
        )
        return f"'{self.class_name()}' has to be an update from one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_conditions())
