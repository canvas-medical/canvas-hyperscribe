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
        "temperature": float,
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
    assert result.temperature == 0.0
    assert result.id == 0


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
        temperature=1.3,
        id=456,
    )

    new_case_id = 999
    result = tested.duplicate_with(case_id=new_case_id)

    assert result.case_id == new_case_id
    assert tested.case_id == 123

    assert result.category == "test_category"
    assert result.turn_total == 10
    assert result.speaker_sequence == ["Clinician", "Patient", "Clinician"]
    assert result.clinician_to_patient_turn_ratio == 1.5
    assert result.mood == [SyntheticCaseMood.PATIENT_FRUSTRATED, SyntheticCaseMood.PATIENT_TEARFUL]
    assert result.pressure == SyntheticCasePressure.TIME_PRESSURE
    assert result.clinician_style == SyntheticCaseClinicianStyle.WARM_CHATTY
    assert result.patient_style == SyntheticCasePatientStyle.ANXIOUS_TALKATIVE
    assert result.turn_buckets == SyntheticCaseTurnBuckets.LONG
    assert result.duration == 15.5
    assert result.text_llm_vendor == "openai"
    assert result.text_llm_name == "gpt-4o"
    assert result.temperature == 1.3
    assert result.id == 456


def test_to_json():
    tests = [
        (
            SyntheticCase(
                case_id=123,
                category="test_category",
                turn_total=3,
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
                temperature=1.3,
                id=456,
            ),
            {
                "case_id": 123,
                "category": "test_category",
                "turnTotal": 3,
                "speakerSequence": ["Clinician", "Patient", "Clinician"],
                "clinicianToPatientTurnRatio": 1.5,
                "mood": ["patient is frustrated", "patient is tearful"],
                "pressure": "time pressure on the visit",
                "clinicianStyle": "warm and chatty",
                "patientStyle": "anxious and talkative",
                "turnBuckets": "long",
                "duration": 15.5,
                "textLlmVendor": "openai",
                "textLlmName": "gpt-4o",
                "temperature": 1.3,
                "id": 456,
            },
        )
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected
