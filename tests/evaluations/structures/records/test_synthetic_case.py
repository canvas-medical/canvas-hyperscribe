from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.records.synthetic_case import SyntheticCase
from tests.helper import is_namedtuple


def test_class():
    tested = SyntheticCase
    fields = {
        "case_id": int,
        "category": str,
        "turn_total": int,
        "speaker_sequence": list[str],
        "clinician_to_patient_turn_ratio": float,
        "mood": list[SyntheticCaseMood],
        "pressure": SyntheticCasePressure,
        "clinician_style": SyntheticCaseClinicianStyle,
        "patient_style": SyntheticCasePatientStyle,
        "turn_buckets": SyntheticCaseTurnBuckets,
        "duration": float,
        "text_llm_vendor": str,
        "text_llm_name": str,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = SyntheticCase(case_id=35)
    assert result.case_id == 35
    assert result.category == ""
    assert result.turn_total == 0
    assert result.speaker_sequence == []
    assert result.clinician_to_patient_turn_ratio == 0.0
    assert result.mood == [SyntheticCaseMood.PATIENT_FRUSTRATED]
    assert result.pressure == SyntheticCasePressure.TIME_PRESSURE
    assert result.clinician_style == SyntheticCaseClinicianStyle.WARM_CHATTY
    assert result.patient_style == SyntheticCasePatientStyle.ANXIOUS_TALKATIVE
    assert result.turn_buckets == SyntheticCaseTurnBuckets.SHORT
    assert result.duration == 0.0
    assert result.text_llm_vendor == ""
    assert result.text_llm_name == ""
    assert result.id == 0
