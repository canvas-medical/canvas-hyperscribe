from typing import Type

from canvas_sdk.commands import PhysicalExamCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.constants import Constants


class PhysicalExam(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PHYSICAL_EXAM

    def include_skipped(self) -> bool:
        return True

    def sdk_command(self) -> Type[PhysicalExamCommand]:
        return PhysicalExamCommand
