from hyperscribe.structures.questionnaire_type import QuestionnaireType


def test_enum():
    tested = QuestionnaireType
    assert len(tested) == 4
    assert tested.QUESTIONNAIRE.value == "QUES"
    assert tested.PHYSICAL_EXAM.value == "EXAM"
    assert tested.REVIEW_OF_SYSTEM.value == "ROS"
    assert tested.STRUCTURED_ASSESSMENT.value == "SA"
