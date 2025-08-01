from evaluations.structures.specification import Specification
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from tests.helper import is_namedtuple


def test_class():
    tested = Specification
    fields = {
        "turn_total": int,
        "speaker_sequence": list[str],
        "ratio": float,
        "mood": list[SyntheticCaseMood],
        "pressure": SyntheticCasePressure,
        "clinician_style": SyntheticCaseClinicianStyle,
        "patient_style": SyntheticCasePatientStyle,
        "bucket": SyntheticCaseTurnBuckets,
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            Specification(
                turn_total=3,
                speaker_sequence=["Clinician", "Patient", "Clinician"],
                ratio=2.0,
                mood=[SyntheticCaseMood.PATIENT_TEARFUL],
                pressure=SyntheticCasePressure.FORMULARY_CHANGE,
                clinician_style=SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
                patient_style=SyntheticCasePatientStyle.AGREEABLE_VAGUE,
                bucket=SyntheticCaseTurnBuckets.SHORT,
            ),
            {
                "turn_total": 3,
                "speaker_sequence": ["Clinician", "Patient", "Clinician"],
                "ratio": 2.0,
                "mood": ["patient is tearful"],
                "pressure": "formulary change",
                "clinician_style": "cautious and inquisitive",
                "patient_style": "agreeable but vague",
                "bucket": "short",
            },
        ),
        (
            Specification(
                turn_total=1,
                speaker_sequence=["Clinician"],
                ratio=1.0,
                mood=[SyntheticCaseMood.PATIENT_FRUSTRATED],
                pressure=SyntheticCasePressure.TIME_PRESSURE,
                clinician_style=SyntheticCaseClinicianStyle.CAUTIOUS_INQUISITIVE,
                patient_style=SyntheticCasePatientStyle.ANXIOUS_TALKATIVE,
                bucket=SyntheticCaseTurnBuckets.SHORT,
            ),
            {
                "turn_total": 1,
                "speaker_sequence": ["Clinician"],
                "ratio": 1.0,
                "mood": ["patient is frustrated"],
                "pressure": "time pressure on the visit",
                "clinician_style": "cautious and inquisitive",
                "patient_style": "anxious and talkative",
                "bucket": "short",
            },
        ),
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected
        assert isinstance(result, dict)


def test_load_from_json():
    tests = [
        (
            {
                "turn_total": 4,
                "speaker_sequence": ["Patient", "Clinician", "Patient", "Clinician"],
                "ratio": 0.8,
                "mood": ["patient is embarrassed"],
                "pressure": "insurance denied prior authorization",
                "clinician_style": "over-explainer",
                "patient_style": "assertive and informed",
                "bucket": "long",
            },
            Specification(
                turn_total=4,
                speaker_sequence=["Patient", "Clinician", "Patient", "Clinician"],
                ratio=0.8,
                mood=[SyntheticCaseMood.PATIENT_EMBARRASSED],
                pressure=SyntheticCasePressure.INSURANCE_DENIED,
                clinician_style=SyntheticCaseClinicianStyle.OVER_EXPLAIN,
                patient_style=SyntheticCasePatientStyle.ASSERTIVE_INFORMED,
                bucket=SyntheticCaseTurnBuckets.LONG,
            ),
        ),
        (
            {
                "turn_total": 2,
                "speaker_sequence": ["Clinician", "Patient"],
                "ratio": 1.0,
                "mood": ["clinician is warm", "clinician is brief"],
                "pressure": "refill limit reached",
                "clinician_style": "warm and chatty",
                "patient_style": "agreeable but vague",
                "bucket": "short",
            },
            Specification(
                turn_total=2,
                speaker_sequence=["Clinician", "Patient"],
                ratio=1.0,
                mood=[SyntheticCaseMood.CLINICIAN_WARM, SyntheticCaseMood.CLINICIAN_BRIEF],
                pressure=SyntheticCasePressure.REFILL_LIMIT,
                clinician_style=SyntheticCaseClinicianStyle.WARM_CHATTY,
                patient_style=SyntheticCasePatientStyle.AGREEABLE_VAGUE,
                bucket=SyntheticCaseTurnBuckets.SHORT,
            ),
        ),
    ]

    for data, expected in tests:
        result = Specification.load_from_json(data)
        assert result == expected
