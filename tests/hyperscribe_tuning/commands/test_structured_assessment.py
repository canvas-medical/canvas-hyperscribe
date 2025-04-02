from hyperscribe_tuning.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe_tuning.commands.structured_assessment import StructuredAssessment


def test_class():
    tested = StructuredAssessment
    assert issubclass(tested, BaseQuestionnaire)


def test_schema_key():
    tested = StructuredAssessment
    result = tested.schema_key()
    expected = "structuredAssessment"
    assert result == expected
