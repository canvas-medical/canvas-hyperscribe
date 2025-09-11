from evaluations.structures.records.score import Score
from evaluations.structures.graded_criterion import GradedCriterion
from tests.helper import is_namedtuple


def test_class():
    tested = Score
    fields = {
        "rubric_id": int,
        "generated_note_id": int,
        "scoring_result": list[GradedCriterion],
        "overall_score": float,
        "comments": str,
        "text_llm_vendor": str,
        "text_llm_name": str,
        "temperature": float,
        "experiment": bool,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = Score(rubric_id=7, generated_note_id=35)
    assert result.rubric_id == 7
    assert result.generated_note_id == 35
    assert result.scoring_result == []
    assert result.overall_score == 0.0
    assert result.comments == ""
    assert result.text_llm_vendor == ""
    assert result.text_llm_name == ""
    assert result.temperature == 0.0
    assert result.id == 0
