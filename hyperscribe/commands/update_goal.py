from canvas_sdk.commands.commands.update_goal import UpdateGoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class UpdateGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_GOAL

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (progress := data.get("progress")) and (goal := data.get("goal_statement", {}).get("text")):
            return CodedItem(label=f"{goal}: {progress}", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        goal_uuid = ""
        if 0 <= (idx := instruction.parameters["goalIndex"]) < len(current := self.cache.current_goals()):
            goal_uuid = current[idx].uuid
            self.add_code2description(current[idx].uuid, current[idx].label)

        return InstructionWithCommand.add_command(
            instruction,
            UpdateGoalCommand(
                goal_id=goal_uuid,
                due_date=Helper.str2datetime(instruction.parameters["dueDate"]),
                achievement_status=Helper.enum_or_none(
                    instruction.parameters["status"],
                    UpdateGoalCommand.AchievementStatus,
                ),
                priority=Helper.enum_or_none(instruction.parameters["priority"], UpdateGoalCommand.Priority),
                progress=instruction.parameters["progressAndBarriers"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "goal": "",
            "goalIndex": -1,
            "dueDate": None,
            "status": "",
            "priority": "",
            "progressAndBarriers": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        goals = [goal.label for goal in self.cache.current_goals()]
        statuses = [status.value for status in UpdateGoalCommand.AchievementStatus]
        priorities = [status.value for status in UpdateGoalCommand.Priority]
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "goal": {
                            "type": "string",
                            "description": "The goal to update",
                            "enum": goals,
                        },
                        "goalIndex": {
                            "type": "integer",
                            "description": "Index of the Goal to update",
                            "minimum": 0,
                            "maximum": len(goals) - 1,
                        },
                        "dueDate": {
                            "type": ["string", "null"],
                            "description": "Due date in YYYY-MM-DD format",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        },
                        "status": {
                            "type": "string",
                            "description": "Achievement status of the goal",
                            "enum": statuses,
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority level of the goal",
                            "enum": priorities,
                        },
                        "progressAndBarriers": {
                            "type": "string",
                            "description": "Progress or barriers, as free text",
                        },
                    },
                    "required": ["goal", "goalIndex", "dueDate", "status", "priority", "progressAndBarriers"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return "Change of status of a previously set goal, including progress, barriers, priority or due date."

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{goal.label}"' for goal in self.cache.current_goals()])
        return f'"{self.class_name()}" has to be related to one of the following goals: {text}'

    def is_available(self) -> bool:
        return bool(self.cache.current_goals())
