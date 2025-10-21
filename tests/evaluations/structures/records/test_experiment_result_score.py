from evaluations.structures.graded_criterion import GradedCriterion
from evaluations.structures.records.experiment_result_score import ExperimentResultScore
from tests.helper import is_namedtuple


def test_class():
    tested = ExperimentResultScore
    fields = {
        "experiment_result_id": int,
        "text_llm_vendor": str,
        "text_llm_name": str,
        "score_id": int,
        "scoring_result": list[GradedCriterion],
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = ExperimentResultScore(133)
    assert result.experiment_result_id == 133
    assert result.text_llm_vendor == ""
    assert result.text_llm_name == ""
    assert result.score_id == 0
    assert result.scoring_result == []
    assert result.id == 0
