from hyperscribe.handlers.constants import Constants
from hyperscribe_tuning.commands.base_questionnaire import BaseQuestionnaire


class PhysicalExam(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PHYSICAL_EXAM
