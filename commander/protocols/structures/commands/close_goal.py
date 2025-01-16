from canvas_sdk.commands.commands.close_goal import CloseGoalCommand
from canvas_sdk.commands.commands.goal import GoalCommand

from commander.protocols.structures.commands.base import Base


class CloseGoal(Base):

    def command_from_json(self, parameters: dict) -> None | CloseGoalCommand:
        goal_uuid = ""
        if 0 <= (idx := parameters["goalIndex"]) < len(self.current_goals()):
            goal_uuid = self.current_goals()[idx].uuid

        return CloseGoalCommand(
            # goal_id=goal_uuid, TODO waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
            achievement_status=GoalCommand.AchievementStatus(parameters["status"]),
            progress=parameters["progressAndBarriers"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        goals = "/".join([f'{goal.label} (index: {idx})' for idx, goal in enumerate(self.current_goals())])
        statuses = "/".join([status.value for status in GoalCommand.AchievementStatus])
        return {
            "goal": f"one of: {goals}",
            "goalIndex": "index of the Goal to close, as integer",
            "status": f"one of: {statuses}",
            "progressAndBarriers": "progress and barriers, as free text",
        }

    def instruction_description(self) -> str:
        return "Final status of a previously set goal, including progress or barriers."

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{goal.label}"' for goal in self.current_goals()])
        return f"'{self.class_name()}' has to be related to one of the following goals: {text}"

    def is_available(self) -> bool:
        return bool(self.current_goals())
