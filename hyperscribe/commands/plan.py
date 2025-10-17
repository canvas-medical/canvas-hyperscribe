from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
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

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        return InstructionWithCommand.add_command(
            instruction,
            PlanCommand(narrative=instruction.parameters["plan"], note_uuid=self.identification.note_uuid),
        )

    def command_parameters(self) -> dict:
        return {
            "plan": (
                "itemized description of the plan of care, including diagnostic steps, treatment steps, self care, "
                "etc, as free text"
            )
        }

    def instruction_description(self) -> str:
        return (
            "Overall treatment plan and care strategy discussed during the visit, including ongoing management, "
            "monitoring approaches, medication strategies, lifestyle modifications, and follow-up scheduling. "
            "This captures the provider's overall approach to the patient's care. "
            "There can be only one plan per instruction, and no instruction if no plan of careis discussed."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
