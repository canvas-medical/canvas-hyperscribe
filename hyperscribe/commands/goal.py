from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Goal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if goal := data.get("goal_statement"):
            return CodedItem(label=goal, code="", uuid="")
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        return InstructionWithCommand.add_command(instruction, GoalCommand(
            goal_statement=instruction.parameters["goal"],
            start_date=Helper.str2datetime(instruction.parameters["startDate"]),
            due_date=Helper.str2datetime(instruction.parameters["dueDate"]),
            achievement_status=Helper.enum_or_none(instruction.parameters["status"], GoalCommand.AchievementStatus),
            priority=Helper.enum_or_none(instruction.parameters["priority"], GoalCommand.Priority),
            progress=instruction.parameters["progressAndBarriers"],
            note_uuid=self.identification.note_uuid,
        ))

    def command_parameters(self) -> dict:
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        priorities = "/".join([status.value for status in GoalCommand.Priority])
        return {
            "goal": "title of the goal, as free text",
            "startDate": "YYYY-MM-DD",
            "dueDate": "YYYY-MM-DD",
            "status": f"one of: {statuses}",
            "priority": f"one of: {priorities}",
            "progressAndBarriers": "progress and barriers, as free text",
        }

    def instruction_description(self) -> str:
        return ("Defined goal set by the provider, including due date and priority. "
                "There can be only one goal per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'"{goal.label}"' for goal in self.cache.current_goals()]):
            result = f'"{self.class_name()}" cannot include: {text}'
        return result

    def is_available(self) -> bool:
        return True
