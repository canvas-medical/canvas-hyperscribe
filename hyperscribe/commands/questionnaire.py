from typing import Type

from canvas_sdk.commands import QuestionnaireCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.constants import Constants


class Questionnaire(BaseQuestionnaire):
    @classmethod
    def command_type(cls) -> str:
        return "QuestionnaireCommand"

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_QUESTIONNAIRE

    def include_skipped(self) -> bool:
        return False

    def sdk_command(self) -> Type[QuestionnaireCommand]:
        return QuestionnaireCommand  # type: ignore
