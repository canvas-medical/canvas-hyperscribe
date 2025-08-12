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


def test_duplicate_with():
    tested = SyntheticCase(
        case_id=123,
        category="test_category",
        turn_total=10,
        speaker_sequence=["Clinician", "Patient", "Clinician"],
        clinician_to_patient_turn_ratio=1.5,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED, SyntheticCaseMood.PATIENT_TEARFUL],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        turn_buckets=SyntheticCaseTurnBuckets.LONG,
        duration=15.5,
        text_llm_vendor="openai",
        text_llm_name="gpt-4o",
        id=456,
    )

    new_case_id = 999
    result = tested.duplicate_with(case_id=new_case_id)

    assert result.case_id == new_case_id
    assert tested.case_id == 123

    assert result.category == tested.category
    assert result.turn_total == tested.turn_total
    assert result.speaker_sequence == tested.speaker_sequence
    assert result.clinician_to_patient_turn_ratio == tested.clinician_to_patient_turn_ratio
    assert result.mood == tested.mood
    assert result.pressure == tested.pressure
    assert result.clinician_style == tested.clinician_style
    assert result.patient_style == tested.patient_style
    assert result.turn_buckets == tested.turn_buckets
    assert result.duration == tested.duration
    assert result.text_llm_vendor == tested.text_llm_vendor
    assert result.text_llm_name == tested.text_llm_name
    assert result.id == tested.id


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
