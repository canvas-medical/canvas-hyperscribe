import json

from evaluations.structures.specification import Specification
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle


def test_specification_creation():
    tested = Specification(
        turn_total=5,
        speaker_sequence=["Clinician", "Patient", "Clinician", "Patient", "Clinician"],
        ratio=1.5,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED, SyntheticCaseMood.CLINICIAN_CONCERNED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.MEDIUM,
    )

    assert tested.turn_total == 5
    assert tested.speaker_sequence == ["Clinician", "Patient", "Clinician", "Patient", "Clinician"]
    assert tested.ratio == 1.5
    assert tested.mood == [SyntheticCaseMood.PATIENT_FRUSTRATED, SyntheticCaseMood.CLINICIAN_CONCERNED]
    assert tested.pressure == SyntheticCasePressure.TIME_PRESSURE
    assert tested.clinician_style == SyntheticCaseClinicianStyle.WARM_CHATTY
    assert tested.patient_style == SyntheticCasePatientStyle.ANXIOUS_TALKATIVE
    assert tested.bucket == SyntheticCaseTurnBuckets.MEDIUM


def test_to_json():
    tested = Specification(
        turn_total=3,
        speaker_sequence=["Clinician", "Patient", "Clinician"],
        ratio=2.0,
        mood=[SyntheticCaseMood.PATIENT_TEARFUL],
        pressure=SyntheticCasePressure.FORMULARY_CHANGE,
        clinician_style=SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        patient_style=SyntheticCasePatientStyle.AGREEABLE_VAGUE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )

    result = tested.to_json()
    expected = {
        "turn_total": 3,
        "speaker_sequence": ["Clinician", "Patient", "Clinician"],
        "ratio": 2.0,
        "mood": ["patient is tearful"],
        "pressure": "formulary change",
        "clinician_style": "cautious and inquisitive",
        "patient_style": "agreeable but vague",
        "bucket": "short",
    }

    assert result == expected
    assert isinstance(result, dict)
    assert len(result) == 8


def test_load_from_json():
    data = {
        "turn_total": 4,
        "speaker_sequence": ["Patient", "Clinician", "Patient", "Clinician"],
        "ratio": 0.8,
        "mood": ["patient is embarrassed"],
        "pressure": "insurance denied prior authorization",
        "clinician_style": "over-explainer",
        "patient_style": "assertive and informed",
        "bucket": "long",
    }

    result = Specification.load_from_json(data)

    assert result.turn_total == 4
    assert result.speaker_sequence == ["Patient", "Clinician", "Patient", "Clinician"]
    assert result.ratio == 0.8
    assert result.mood == [SyntheticCaseMood.PATIENT_EMBARRASSED]
    assert result.pressure == SyntheticCasePressure.INSURANCE_DENIED
    assert result.clinician_style == SyntheticCaseClinicianStyle.OVER_EXPLAIN
    assert result.patient_style == SyntheticCasePatientStyle.ASSERTIVE_INFORMED
    assert result.bucket == SyntheticCaseTurnBuckets.LONG


def test_round_trip_serialization():
    original = Specification(
        turn_total=6,
        speaker_sequence=["Clinician", "Patient", "Patient", "Clinician", "Patient", "Clinician"],
        ratio=1.2,
        mood=[SyntheticCaseMood.PATIENT_DEFENSIVE, SyntheticCaseMood.CLINICIAN_RUSHED],
        pressure=SyntheticCasePressure.PATIENT_TRAVELS,
        clinician_style=SyntheticCaseClinicianStyle.BRIEF_EFFICIENT,
        patient_style=SyntheticCasePatientStyle.CONFUSED_FORGETFUL,
        bucket=SyntheticCaseTurnBuckets.MEDIUM,
    )

    json_data = original.to_json()
    result = Specification.load_from_json(json_data)

    assert result == original
    assert result.to_json() == original.to_json()


def test_json_serializable():
    tested = Specification(
        turn_total=2,
        speaker_sequence=["Clinician", "Patient"],
        ratio=1.0,
        mood=[SyntheticCaseMood.CLINICIAN_WARM],
        pressure=SyntheticCasePressure.REFILL_LIMIT,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.AGREEABLE_VAGUE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )

    json_result = tested.to_json()

    # Should be JSON serializable
    json_str = json.dumps(json_result)
    parsed_back = json.loads(json_str)

    assert parsed_back == json_result
    assert Specification.load_from_json(parsed_back) == tested


def test_multiple_moods():
    tested = Specification(
        turn_total=3,
        speaker_sequence=["Clinician", "Patient", "Clinician"],
        ratio=1.5,
        mood=[
            SyntheticCaseMood.PATIENT_FRUSTRATED,
            SyntheticCaseMood.PATIENT_TEARFUL,
            SyntheticCaseMood.CLINICIAN_CONCERNED,
        ],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.MEDIUM,
    )

    json_data = tested.to_json()
    expected_moods = ["patient is frustrated", "patient is tearful", "clinician is concerned"]

    assert json_data["mood"] == expected_moods

    result = Specification.load_from_json(json_data)
    assert result.mood == tested.mood


def test_enum_value_conversion():
    # Test that enum values are properly converted to strings in to_json
    tested = Specification(
        turn_total=1,
        speaker_sequence=["Clinician"],
        ratio=1.0,
        mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
        pressure=SyntheticCasePressure.TIME_PRESSURE,
        clinician_style=SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
        patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
        bucket=SyntheticCaseTurnBuckets.SHORT,
    )

    json_data = tested.to_json()

    # All enum values should be converted to strings
    assert isinstance(json_data["mood"][0], str)
    assert isinstance(json_data["pressure"], str)
    assert isinstance(json_data["clinician_style"], str)
    assert isinstance(json_data["patient_style"], str)
    assert isinstance(json_data["bucket"], str)

    # Values should match enum .value attributes
    assert json_data["mood"][0] == SyntheticCaseMood.PATIENT_FRUSTRATED.value
    assert json_data["pressure"] == SyntheticCasePressure.TIME_PRESSURE.value
    assert json_data["clinician_style"] == SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE.value
    assert json_data["patient_style"] == SyntheticCasePatientStyle.ANXIOUS_TALKATIVE.value
    assert json_data["bucket"] == SyntheticCaseTurnBuckets.SHORT.value
