from canvas_sdk.commands.commands.resolve_condition import ResolveConditionCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class ResolveCondition(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_RESOLVE_CONDITION

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_ASSESSMENT

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative")
        if condition := data.get("condition", {}).get("text"):
            return CodedItem(label=f"{condition}: {narrative}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        condition_id = ""
        if 0 <= (idx := instruction.parameters["conditionIndex"]) < len(current := self.cache.current_conditions()):
            condition_id = current[idx].uuid
            self.add_code2description(current[idx].uuid, current[idx].label)

        return InstructionWithCommand.add_command(
            instruction,
            ResolveConditionCommand(
                condition_id=condition_id,
                rationale=instruction.parameters["rationale"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "condition": "",
            "conditionIndex": -1,
            "rationale": "",
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
                        "condition": {
                            "type": "string",
                            "description": "The condition to set as resolved",
                            "enum": conditions,
                        },
                        "conditionIndex": {
                            "type": "integer",
                            "description": "Index of the Condition to set as resolved",
                            "minimum": 0,
                            "maximum": len(conditions) - 1,
                        },
                        "rationale": {
                            "type": "string",
                            "description": "Rationale to set the condition as resolved, as free text",
                        },
                    },
                    "required": ["condition", "conditionIndex", "rationale"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        text = ", ".join([f"{condition.label}" for condition in self.cache.current_conditions()])
        return (
            f"Set as resolved a previously diagnosed condition ({text}). "
            "There can be only one resolved condition per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join(
            [f"{condition.label} (ICD-10: {condition.code})" for condition in self.cache.current_conditions()],
        )
        return f"'{self.class_name()}' has to be related to one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_conditions())
