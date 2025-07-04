from evaluations.structures.enums.rubric_validation import RubricValidation


def test_enum():
    tested = RubricValidation
    assert len(tested) == 3
    assert tested.NOT_EVALUATED.value == "not_evaluated"
    assert tested.REFUSED.value == "refused"
    assert tested.ACCEPTED.value == "accepted"
