from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets


def test_enum():
    tested = SyntheticCaseTurnBuckets
    assert len(tested) == 3
    assert tested.SHORT.value == "short"
    assert tested.MEDIUM.value == "medium"
    assert tested.LONG.value == "long"
