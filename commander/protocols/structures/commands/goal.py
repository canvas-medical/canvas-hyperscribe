from canvas_sdk.commands.commands.goal import GoalCommand

from commander.protocols.structures.commands.base import Base


class Goal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "goal"

    def command_from_json(self, parameters: dict) -> None | GoalCommand:
        return GoalCommand(
            goal_statement=parameters["goal"],
            start_date=self.str2datetime(parameters["startDate"]),
            due_date=self.str2datetime(parameters["dueDate"]),
            achievement_status=self.enum_or_none(parameters["status"], GoalCommand.AchievementStatus),
            priority=self.enum_or_none(parameters["priority"], GoalCommand.Priority),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

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
        text = ", ".join([f'"{goal.label}"' for goal in self.current_goals()])
        return f"'{self.class_name()}' cannot include: {text}"

    def is_available(self) -> bool:
        return True
