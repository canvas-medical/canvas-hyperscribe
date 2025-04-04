from canvas_sdk.commands import StructuredAssessmentCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.handlers.constants import Constants
from hyperscribe.llms.llm_base import LlmBase


class StructuredAssessment(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_STRUCTURED_ASSESSMENT

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | StructuredAssessmentCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
