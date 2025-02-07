from canvas_sdk.commands.commands.assess import AssessCommand

from commander.protocols.commands.base import Base
from commander.protocols.helper import Helper


class Assess(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "assess"

    def command_from_json(self, parameters: dict) -> None | AssessCommand:
        condition_id = ""
        if 0 <= (idx := parameters["conditionIndex"]) < len(current := self.current_conditions()):
            condition_id = current[idx].uuid
        return AssessCommand(
            condition_id=condition_id,
            background=parameters["rationale"],
            status=Helper.enum_or_none(parameters["status"], AssessCommand.Status),
            narrative=parameters["assessment"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        statuses = "/".join([status.value for status in AssessCommand.Status])
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])
        return {
            "condition": f"one of: {conditions}",
            "conditionIndex": "index of the Condition to assess, as integer",
            "rationale": "rationale about the current assessment, as free text",
            "status": f"one of: {statuses}",
            "assessment": "today's assessment of the condition, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{condition.label}' for condition in self.current_conditions()])
        return (f"Today's assessment of a diagnosed condition ({text}). "
                "There can be only one assessment per condition per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{condition.label} (ICD-10: {condition.code})' for condition in self.current_conditions()])
        return f"'{self.class_name()}' has to be related to one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.current_conditions())
