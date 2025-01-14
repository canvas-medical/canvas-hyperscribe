from canvas_sdk.commands.commands.goal import GoalCommand

from commander.protocols.structures.commands.base import Base


class Goal(Base):
    def from_json(self, parameters: dict) -> None | GoalCommand:
        return GoalCommand(
            goal_statement=parameters["goal"],
            start_date=self.str2date(parameters["startDate"]),
            due_date=self.str2date(parameters["dueDate"]),
            achievement_status=GoalCommand.AchievementStatus(parameters["status"]),
            priority=GoalCommand.Priority(parameters["priority"]),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        priorities = "/".join([status.value for status in GoalCommand.Priority])
        return {
            "goal": "free text",
            "startDate": "YYYY-MM-DD",
            "dueDate": "YYYY-MM-DD",
            "status": statuses,
            "priority": priorities,
            "progressAndBarriers": "free text",
        }

    def information(self) -> str:
        return ("Defined goal set by the provider, including due date and priority. "
                "There can be only one goal per instruction, and no instruction in the lack of.")

    def constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
