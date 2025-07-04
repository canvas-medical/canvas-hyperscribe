from evaluations.structures.enums.case_status import CaseStatus


def test_enum():
    tested = CaseStatus
    assert len(tested) == 3
    assert tested.GENERATION.value == "generation"
    assert tested.REVIEW.value == "review"
    assert tested.EVALUATION.value == "evaluation"
