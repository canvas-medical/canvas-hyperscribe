from canvas_sdk.commands.commands.goal import GoalCommand
from canvas_sdk.commands.commands.update_goal import UpdateGoalCommand

from commander.protocols.structures.commands.base import Base


class UpdateGoal(Base):

    def command_from_json(self, parameters: dict) -> None | UpdateGoalCommand:
        goal_uuid = ""
        if 0 <= (idx := parameters["goalIndex"]) < len(self.current_goals()):
            goal_uuid = self.current_goals()[idx].uuid

        return UpdateGoalCommand(
            goal_id=goal_uuid,
            due_date=self.str2date(parameters["dueDate"]),
            achievement_status=GoalCommand.AchievementStatus(parameters["status"]),
            priority=GoalCommand.Priority(parameters["priority"]),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        goals = "/".join([f'{goal.label} (index: {idx})' for idx, goal in enumerate(self.current_goals())])
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        priorities = "/".join([status.value for status in GoalCommand.Priority])
        return {
            "goal": f"one of: {goals}",
            "goalIndex": "index of the Goal to update, as integer",
            "dueDate": "YYYY-MM-DD",
            "status": f"one of: {statuses}",
            "priority": f"one of: {priorities}",
            "progressAndBarriers": "progress or barriers, as free text",
        }

    def instruction_description(self) -> str:
        return "Current status of a previously set goal, including progress or barriers."

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{goal.label}"' for goal in self.current_goals()])
        return f"'{self.class_name()}' has to be related to one of the following goals: {text}"

    def is_available(self) -> bool:
        return bool(self.current_goals())
