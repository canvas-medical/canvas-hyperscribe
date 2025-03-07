from canvas_sdk.commands.commands.close_goal import CloseGoalCommand
from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem


class CloseGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_CLOSE_GOAL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := (data.get("goal_id") or {}).get("text"):
            return CodedItem(label=f'{text} ({data.get("progress") or "n/a"})', code="", uuid="")
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | CloseGoalCommand:
        goal_uuid = "0"
        if 0 <= (idx := parameters["goalIndex"]) < len(current := self.cache.current_goals()):
            # TODO should be  goal_uuid = current[idx].uuid, waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
            goal_uuid = current[idx].code

        return CloseGoalCommand(
            # TODO should be goal_id=goal_uuid, waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
            goal_id=int(goal_uuid),
            achievement_status=Helper.enum_or_none(parameters["status"], GoalCommand.AchievementStatus),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        goals = "/".join([f'{goal.label} (index: {idx})' for idx, goal in enumerate(self.cache.current_goals())])
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        return {
            "goal": f"one of: {goals}",
            "goalIndex": "index of the Goal to close, or -1, as integer",
            "status": f"one of: {statuses}",
            "progressAndBarriers": "progress and barriers, as free text",
        }

    def instruction_description(self) -> str:
        return "Ending of a previously set goal, including status, progress, barriers, priority or due date."

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{goal.label}"' for goal in self.cache.current_goals()])
        return f'"{self.class_name()}" has to be related to one of the following goals: {text}'

    def is_available(self) -> bool:
        return bool(self.cache.current_goals())
