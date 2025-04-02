from hyperscribe_tuning.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe_tuning.commands.questionnaire import Questionnaire


def test_class():
    tested = Questionnaire
    assert issubclass(tested, BaseQuestionnaire)


def test_schema_key():
    tested = Questionnaire
    result = tested.schema_key()
    expected = "questionnaire"
    assert result == expected
