from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Plan(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if text := data.get("narrative"):
            return CodedItem(label=text, code="", uuid="")
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        return InstructionWithCommand.add_command(instruction, PlanCommand(
            narrative=instruction.parameters["plan"],
            note_uuid=self.note_uuid,
        ))

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
