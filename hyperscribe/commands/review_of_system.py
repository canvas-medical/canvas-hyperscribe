from typing import Type

from canvas_sdk.commands import ReviewOfSystemsCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.constants import Constants


class ReviewOfSystem(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REVIEW_OF_SYSTEM

    def include_skipped(self) -> bool:
        return True

    def sdk_command(self) -> Type[ReviewOfSystemsCommand]:
        return ReviewOfSystemsCommand
