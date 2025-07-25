from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle


def test_enum():
    tested = SyntheticCasePatientStyle
    assert len(tested) == 4
    assert tested.ANXIOUS_TALKATIVE.value == "anxious and talkative"
    assert tested.CONFUSED_FORGETFUL.value == "confused and forgetful"
    assert tested.ASSERTIVE_INFORMED.value == "assertive and informed"
    assert tested.AGREEABLE_VAGUE.value == "agreeable but vague"
