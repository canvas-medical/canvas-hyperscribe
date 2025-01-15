from canvas_sdk.commands.commands.close_goal import CloseGoalCommand
from canvas_sdk.commands.commands.goal import GoalCommand

from commander.protocols.structures.commands.base import Base


class CloseGoal(Base):

    def command_from_json(self, parameters: dict) -> None | CloseGoalCommand:
        return CloseGoalCommand(
            goal_id=parameters["goal"],
            achievement_status=GoalCommand.AchievementStatus(parameters["status"]),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        return {
            "goal": "Name of the Goal to close",
            "status": statuses,
            "progressAndBarriers": "free text",
        }

    def instruction_description(self) -> str:
        return "Final status of a previously set goal, including progress or barriers."

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return bool(self.current_goals())
