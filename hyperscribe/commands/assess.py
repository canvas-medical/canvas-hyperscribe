from canvas_sdk.commands.commands.assess import AssessCommand

from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Assess(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ASSESS

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (narrative := data.get("narrative")) and (condition := data.get("condition", {}).get("text")):
            return CodedItem(label=f'{condition}: {narrative}', code="", uuid="")
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        condition_id = ""
        if 0 <= (idx := instruction.parameters["conditionIndex"]) < len(current := self.cache.current_conditions()):
            condition_id = current[idx].uuid
        return InstructionWithCommand.add_command(instruction, AssessCommand(
            condition_id=condition_id,
            background=instruction.parameters["rationale"],
            status=Helper.enum_or_none(instruction.parameters["status"], AssessCommand.Status),
            narrative=instruction.parameters["assessment"],
            note_uuid=self.note_uuid,
        ))

    def command_parameters(self) -> dict:
        statuses = "/".join([status.value for status in AssessCommand.Status])
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.cache.current_conditions())])
        return {
            "condition": f"one of: {conditions}",
            "conditionIndex": "index of the Condition to assess, or -1, as integer",
            "rationale": "rationale about the current assessment, as free text",
            "status": f"one of: {statuses}",
            "assessment": "today's assessment of the condition, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{condition.label}' for condition in self.cache.current_conditions()])
        return (f"Today's assessment of a diagnosed condition ({text}). "
                "There can be only one assessment per condition per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{condition.label} (ICD-10: {condition.code})' for condition in self.cache.current_conditions()])
        return f"'{self.class_name()}' has to be related to one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_conditions())
