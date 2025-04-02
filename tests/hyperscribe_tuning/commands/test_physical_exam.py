from hyperscribe_tuning.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe_tuning.commands.physical_exam import PhysicalExam


def test_class():
    tested = PhysicalExam
    assert issubclass(tested, BaseQuestionnaire)


def test_schema_key():
    tested = PhysicalExam
    result = tested.schema_key()
    expected = "exam"
    assert result == expected
