from canvas_sdk.commands.commands.exam import PhysicalExamCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.handlers.constants import Constants
from hyperscribe.llms.llm_base import LlmBase


class PhysicalExam(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PHYSICAL_EXAM

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | PhysicalExamCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
