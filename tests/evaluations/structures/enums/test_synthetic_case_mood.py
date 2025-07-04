from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood


def test_enum():
    tested = SyntheticCaseMood
    assert len(tested) == 3
    assert tested.NEUTRAL.value == "neutral"
    assert tested.HAPPY.value == "happy"
    assert tested.DEPRESSED.value == "depressed"
