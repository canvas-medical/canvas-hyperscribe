from evaluations.structures.records.experiment_result import ExperimentResult
from tests.helper import is_namedtuple


def test_class():
    tested = ExperimentResult
    fields = {
        "experiment_id": int,
        "experiment_name": str,
        "hyperscribe_version": str,
        "hyperscribe_tags": dict,
        "case_id": int,
        "case_name": str,
        "text_llm_vendor": str,
        "text_llm_name": str,
        "cycle_time": int,
        "cycle_transcript_overlap": int,
        "failed": bool,
        "errors": dict,
        "generated_note_id": int,
        "note_json": list,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = ExperimentResult(77)
    assert result.experiment_id == 77
    assert result.experiment_name == ""
    assert result.hyperscribe_version == ""
    assert result.hyperscribe_tags == {}
    assert result.case_id == 0
    assert result.case_name == ""
    assert result.text_llm_vendor == ""
    assert result.text_llm_name == ""
    assert result.cycle_time == 0
    assert result.cycle_transcript_overlap == 0
    assert result.failed == False
    assert result.errors == {}
    assert result.generated_note_id == 0
    assert result.note_json == []
    assert result.id == 0
