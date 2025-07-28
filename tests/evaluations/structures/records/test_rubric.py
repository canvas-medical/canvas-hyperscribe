from datetime import datetime

from evaluations.structures.enums.rubric_validation import RubricValidation
from evaluations.structures.records.rubric import Rubric
from tests.helper import is_namedtuple


def test_class():
    tested = Rubric
    fields = {
        "case_id": int,
        "parent_rubric_id": int | None,
        "validation_timestamp": datetime | None,
        "validation": RubricValidation,
        "author": str,
        "rubric": list[dict],
        "case_provenance_classification": str,
        "comments": str,
        "text_llm_vendor": str,
        "text_llm_name": str,
        "temperature": float,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = Rubric(case_id=7)
    assert result.case_id == 7
    assert result.parent_rubric_id is None
    assert result.validation_timestamp is None
    assert result.validation == RubricValidation.NOT_EVALUATED
    assert result.author == ""
    assert result.rubric == []
    assert result.case_provenance_classification == ""
    assert result.comments == ""
    assert result.text_llm_vendor == ""
    assert result.text_llm_name == ""
    assert result.temperature == 0.0
    assert result.id == 0
