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
        return InstructionWithCommand.add_command(
            instruction,
            ResolveConditionCommand(
                condition_id=condition_id,
                rationale=instruction.parameters["rationale"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        conditions = "/".join(
            [f"{condition.label} (index: {idx})" for idx, condition in enumerate(self.cache.current_conditions())],
        )
        return {
            "condition": f"one of: {conditions}",
            "conditionIndex": "index of the Condition to set as resolved, or -1, as integer",
            "rationale": "rationale to set the condition as resolved, as free text",
        }

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
