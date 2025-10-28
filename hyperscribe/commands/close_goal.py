from canvas_sdk.commands.commands.close_goal import CloseGoalCommand
from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class CloseGoal(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_CLOSE_GOAL

    @classmethod
    def note_section(cls) -> str:
        return Constants.SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := (data.get("goal_id") or {}).get("text"):
            return CodedItem(label=f"{text} ({data.get('progress') or 'n/a'})", code="", uuid="")
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        goal_uuid = "0"
        if 0 <= (idx := instruction.parameters["goalIndex"]) < len(current := self.cache.current_goals()):
            # TODO should be  goal_uuid = current[idx].uuid, waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
            goal_uuid = current[idx].code
            self.add_code2description(current[idx].code, current[idx].label)

        return InstructionWithCommand.add_command(
            instruction,
            CloseGoalCommand(
                # TODO should be goal_id=goal_uuid, waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
                goal_id=int(goal_uuid),
                achievement_status=Helper.enum_or_none(instruction.parameters["status"], GoalCommand.AchievementStatus),
                progress=instruction.parameters["progressAndBarriers"],
                note_uuid=self.identification.note_uuid,
            ),
        )

    def command_parameters(self) -> dict:
        return {
            "goal": "",
            "goalIndex": -1,
            "status": "",
            "progressAndBarriers": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        goals = [goal.label for goal in self.cache.current_goals()]
        statuses = [status.value for status in GoalCommand.AchievementStatus]
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
                            "description": "The goal to close",
                            "enum": goals,
                        },
                        "goalIndex": {
                            "type": "integer",
                            "description": "Index of the Goal to close",
                            "minimum": 0,
                            "maximum": len(goals) - 1,
                        },
                        "status": {
                            "type": "string",
                            "description": "Achievement status of the goal",
                            "enum": statuses,
                        },
                        "progressAndBarriers": {
                            "type": "string",
                            "description": "Progress and barriers, as free text",
                        },
                    },
                    "required": ["goal", "goalIndex", "status", "progressAndBarriers"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return "Ending of a previously set goal, including status, progress, barriers, priority or due date."

    def instruction_constraints(self) -> str:
        text = ", ".join([f'"{goal.label}"' for goal in self.cache.current_goals()])
        return f'"{self.class_name()}" has to be related to one of the following goals: {text}'

    def is_available(self) -> bool:
        return bool(self.cache.current_goals())
