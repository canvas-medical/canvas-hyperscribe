from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle


def test_enum():
    tested = SyntheticCaseClinicianStyle
    assert len(tested) == 4
    assert tested.WARM_CHATTY.value == "warm and chatty"
    assert tested.BRIEF_EFFICIENT.value == "brief and efficient"
    assert tested.CAUTIOUS_INQUISITIVE.value == "cautious and inquisitive"
    assert tested.OVER_EXPLAIN.value == "over-explainer"
