from canvas_sdk.commands.commands.resolve_condition import ResolveConditionCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem


class ResolveCondition(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_RESOLVE_CONDITION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        narrative = data.get("narrative")
        if condition := data.get("condition", {}).get("text"):
            return CodedItem(label=f'{condition}: {narrative}', code="", uuid="")
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | ResolveConditionCommand:
        condition_id = ""
        if 0 <= (idx := parameters["conditionIndex"]) < len(current := self.cache.current_conditions()):
            condition_id = current[idx].uuid
        return ResolveConditionCommand(
            condition_id=condition_id,
            rationale=parameters["rationale"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.cache.current_conditions())])
        return {
            "condition": f"one of: {conditions}",
            "conditionIndex": "index of the Condition to set as resolved, or -1, as integer",
            "rationale": "rationale to set the condition as resolved, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{condition.label}' for condition in self.cache.current_conditions()])
        return (f"Set as resolved a previously diagnosed condition ({text}). "
                "There can be only one resolved condition per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{condition.label} (ICD-10: {condition.code})' for condition in self.cache.current_conditions()])
        return f"'{self.class_name()}' has to be related to one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_conditions())
