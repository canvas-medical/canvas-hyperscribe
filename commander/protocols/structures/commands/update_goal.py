from canvas_sdk.commands.commands.goal import GoalCommand
from canvas_sdk.commands.commands.update_goal import UpdateGoalCommand

from commander.protocols.structures.commands.base import Base


class UpdateGoal(Base):

    def command_from_json(self, parameters: dict) -> None | UpdateGoalCommand:
        return UpdateGoalCommand(
            goal_id=parameters["goal"],
            due_date=self.str2date(parameters["dueDate"]),
            achievement_status=GoalCommand.AchievementStatus(parameters["status"]),
            priority=GoalCommand.Priority(parameters["priority"]),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        priorities = "/".join([status.value for status in GoalCommand.Priority])
        return {
            "goal": "Name of the Goal to update",
            "dueDate": "YYYY-MM-DD",
            "status": statuses,
            "priority": priorities,
            "progressAndBarriers": "free text",
        }

    def instruction_description(self) -> str:
        return "Current status of a previously set goal, including progress or barriers."

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return bool(self.current_goals())
