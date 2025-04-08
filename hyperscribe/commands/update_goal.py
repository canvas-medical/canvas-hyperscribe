from canvas_sdk.commands.commands.update_goal import UpdateGoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class UpdateGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (progress := data.get("progress")) and (goal := data.get("goal_statement", {}).get("text")):
            return CodedItem(label=f'{goal}: {progress}', code="", uuid="")
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        goal_uuid = ""
        if 0 <= (idx := instruction.parameters["goalIndex"]) < len(current := self.cache.current_goals()):
            goal_uuid = current[idx].uuid

        return InstructionWithCommand.add_command(instruction, UpdateGoalCommand(
            goal_id=goal_uuid,
            due_date=Helper.str2datetime(instruction.parameters["dueDate"]),
            achievement_status=Helper.enum_or_none(instruction.parameters["status"], UpdateGoalCommand.AchievementStatus),
            priority=Helper.enum_or_none(instruction.parameters["priority"], UpdateGoalCommand.Priority),
            progress=instruction.parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        ))

    def command_parameters(self) -> dict:
        goals = "/".join([f'{goal.label} (index: {idx})' for idx, goal in enumerate(self.cache.current_goals())])
        statuses = "/".join([status.value for status in UpdateGoalCommand.AchievementStatus])
        priorities = "/".join([status.value for status in UpdateGoalCommand.Priority])
        return {
            "goal": f"one of: {goals}",
            "goalIndex": "index of the Goal to update, or -1, as integer",
            "dueDate": "YYYY-MM-DD",
            "status": f"one of: {statuses}",
            "priority": f"one of: {priorities}",
            "progressAndBarriers": "progress or barriers, as free text",
        }

    def instruction_description(self) -> str:
        return "Change of status of a previously set goal, including progress, barriers, priority or due date."

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{goal.label}"' for goal in self.cache.current_goals()])
        return f'"{self.class_name()}" has to be related to one of the following goals: {text}'

    def is_available(self) -> bool:
        return bool(self.cache.current_goals())
