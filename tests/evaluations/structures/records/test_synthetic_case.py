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
        "speaker_sequence": str,
        "clinician_to_patient_turn_ratio": float,
        "mood": SyntheticCaseMood,
        "pressure": SyntheticCasePressure,
        "clinician_style": SyntheticCaseClinicianStyle,
        "patient_style": SyntheticCasePatientStyle,
        "turn_buckets": SyntheticCaseTurnBuckets,
        "duration": float,
        "audio_llm_vendor": str,
        "audio_llm_name": str,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = SyntheticCase(case_id=35)
    assert result.case_id == 35
    assert result.category == ""
    assert result.turn_total == 0
    assert result.speaker_sequence == ""
    assert result.clinician_to_patient_turn_ratio == 0.0
    assert result.mood == SyntheticCaseMood.NEUTRAL
    assert result.pressure == SyntheticCasePressure.NEUTRAL
    assert result.clinician_style == SyntheticCaseClinicianStyle.NEUTRAL
    assert result.patient_style == SyntheticCasePatientStyle.NEUTRAL
    assert result.turn_buckets == SyntheticCaseTurnBuckets.NEUTRAL
    assert result.duration == 0.0
    assert result.audio_llm_vendor == ""
    assert result.audio_llm_name == ""
    assert result.id == 0
