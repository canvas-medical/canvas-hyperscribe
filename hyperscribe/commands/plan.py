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
            "plan": "detailed description of the treatment plan in free text, including specific medications, doses, "
            "follow-up dates/times, alternative options discussed, contingency plans, and ongoing interventions"
        }

    def instruction_description(self) -> str:
        return (
            "Comprehensive treatment plan capturing all agreed-upon actions and future care decisions. "
            "Include: (1) medication changes (specific doses, timing, formulations), (2) exact follow-up schedule "
            "(specific dates/times if discussed, not just timeframes like 'a couple months'), (3) alternative treatment "
            "options mentioned for future consideration, (4) contingency plans (e.g., 'contact sooner if symptoms worsen'), "
            "(5) ongoing interventions (therapy, monitoring, lifestyle modifications), and (6) important patient-specific "
            "considerations discussed that may impact treatment (e.g., pregnancy planning, long-term medication concerns). "
            "Capture specific details from the conversation rather than generic summaries. "
            "There can be only one plan per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
