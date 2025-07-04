from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle


def test_enum():
    tested = SyntheticCaseClinicianStyle
    assert len(tested) == 3
    assert tested.NEUTRAL.value == "neutral"
    assert tested.FRIENDLY.value == "friendly"
    assert tested.FORMAL.value == "formal"
