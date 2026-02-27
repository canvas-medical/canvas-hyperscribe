from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Goal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_GOAL

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if goal := data.get("goal_statement"):
            return CodedItem(label=goal, code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        # Get field values with template permission checks
        goal_statement = self.resolve_field("goal_statement", instruction.parameters["goal"], instruction, chatter)
        progress = self.resolve_field("progress", instruction.parameters["progressAndBarriers"], instruction, chatter)

        # If neither field can be edited, skip this command
        if goal_statement is None and progress is None:
            return None

        return InstructionWithCommand.add_command(
            instruction,
            GoalCommand(
                goal_statement=goal_statement or "",
                start_date=Helper.str2date(instruction.parameters["startDate"]),
                due_date=Helper.str2date(instruction.parameters["dueDate"]),
                achievement_status=Helper.enum_or_none(instruction.parameters["status"], GoalCommand.AchievementStatus),
                priority=Helper.enum_or_none(instruction.parameters["priority"], GoalCommand.Priority),
                progress=progress or "",
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "goal": "",
            "startDate": None,
            "dueDate": None,
            "status": "",
            "priority": "",
            "progressAndBarriers": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        statuses = [status.value for status in GoalCommand.AchievementStatus]
        priorities = [status.value for status in GoalCommand.Priority]
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
                            "description": "Title of the goal, as free text",
                        },
                        "startDate": {
                            "type": ["string", "null"],
                            "description": "Start date in YYYY-MM-DD format",
                            "format": "date",
                            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
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
                            "description": "Progress and barriers, as free text",
                        },
                    },
                    "required": ["goal", "startDate", "dueDate", "status", "priority", "progressAndBarriers"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "Defined goal set by the provider, including due date and priority. "
            "There can be only one goal per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'"{goal.label}"' for goal in self.cache.current_goals()]):
            result = f"Only document '{self.class_name()}' for goals outside the following list: {text}."
        return result

    def is_available(self) -> bool:
        return True
