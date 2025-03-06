from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem


class Plan(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := data.get("narrative"):
            return CodedItem(label=text, code="", uuid="")
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | PlanCommand:
        return PlanCommand(
            narrative=parameters["plan"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        return {
            "plan": "description of the plan, as free text",
        }

    def instruction_description(self) -> str:
        return ("Defined plan for future patient visits. "
                "There can be only one plan per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
