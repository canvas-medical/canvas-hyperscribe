from evaluations.structures.patient_profile import PatientProfile
from tests.helper import is_namedtuple


def test_class():
    tested = PatientProfile
    fields = {
        "name": str,
        "profile": str,
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            PatientProfile(
                name="Jane Smith",
                profile="45-year-old female with hypertension and asthma. Well-controlled on current medications.",
            ),
            {
                "name": "Jane Smith",
                "profile": "45-year-old female with hypertension and asthma. Well-controlled on current medications.",
            },
        ),
        (
            PatientProfile(name="", profile=""),
            {"name": "", "profile": ""},
        ),
        (
            PatientProfile(
                name="Patient with Long History",
                profile="Complex 72-year-old patient with multiple comorbidities including diabetes mellitus type 2.",
            ),
            {
                "name": "Patient with Long History",
                "profile": "Complex 72-year-old patient with multiple comorbidities"
                " including diabetes mellitus type 2.",
            },
        ),
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected


def test_load_from_json():
    tests = [
        (
            {
                "Bob Johnson": "30-year-old male, healthy, no current medications. Routine check-up.",
                "Alice Brown": "55-year-old female with osteoarthritis. Takes ibuprofen as needed for joint pain.",
            },
            [
                PatientProfile(
                    name="Bob Johnson",
                    profile="30-year-old male, healthy, no current medications. Routine check-up.",
                ),
                PatientProfile(
                    name="Alice Brown",
                    profile="55-year-old female with osteoarthritis. Takes ibuprofen as needed for joint pain.",
                ),
            ],
        ),
        (
            {"Patient 1": "Profile text 1", "Patient 2": "Profile text 2"},
            [
                PatientProfile(name="Patient 1", profile="Profile text 1"),
                PatientProfile(name="Patient 2", profile="Profile text 2"),
            ],
        ),
        (
            {},
            [],
        ),
    ]

    for data, expected in tests:
        result = PatientProfile.load_from_json(data)
        assert result == expected
