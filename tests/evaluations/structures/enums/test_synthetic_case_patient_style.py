from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle


def test_enum():
    tested = SyntheticCasePatientStyle
    assert len(tested) == 3
    assert tested.NEUTRAL.value == "neutral"
    assert tested.FRIENDLY.value == "friendly"
    assert tested.FORMAL.value == "formal"
