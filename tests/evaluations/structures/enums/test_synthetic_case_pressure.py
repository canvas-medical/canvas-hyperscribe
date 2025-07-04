from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure


def test_enum():
    tested = SyntheticCasePressure
    assert len(tested) == 3
    assert tested.NEUTRAL.value == "neutral"
    assert tested.LOW.value == "low"
    assert tested.HIGH.value == "high"
