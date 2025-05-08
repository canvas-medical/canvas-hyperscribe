from hyperscribe_tuning.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe_tuning.handlers.constants import Constants


class Questionnaire(BaseQuestionnaire):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_QUESTIONNAIRE
