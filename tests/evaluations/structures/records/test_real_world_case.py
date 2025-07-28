from evaluations.structures.records.real_world_case import RealWorldCase
from tests.helper import is_namedtuple


def test_class():
    tested = RealWorldCase
    fields = {
        "case_id": int,
        "customer_identifier": str,
        "patient_note_hash": str,
        "topical_exchange_identifier": str,
        "publishable": bool,
        "start_time": float,
        "end_time": float,
        "duration": float,
        "audio_llm_vendor": str,
        "audio_llm_name": str,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = RealWorldCase(case_id=7)
    assert result.case_id == 7
    assert result.customer_identifier == ""
    assert result.patient_note_hash == ""
    assert result.topical_exchange_identifier == ""
    assert result.publishable is False
    assert result.start_time == 0.0
    assert result.end_time == 0.0
    assert result.duration == 0.0
    assert result.audio_llm_vendor == ""
    assert result.audio_llm_name == ""
    assert result.id == 0
