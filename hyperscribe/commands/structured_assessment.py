from typing import Type

from canvas_sdk.commands import StructuredAssessmentCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.constants import Constants


class StructuredAssessment(BaseQuestionnaire):
    @classmethod
    def command_type(cls) -> str:
        return "StructuredAssessmentCommand"

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_STRUCTURED_ASSESSMENT

    def include_skipped(self) -> bool:
        return False

    def sdk_command(self) -> Type[StructuredAssessmentCommand]:
        return StructuredAssessmentCommand  # type: ignore
