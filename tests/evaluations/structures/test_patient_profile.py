import json

from evaluations.structures.patient_profile import PatientProfile


def test_patient_profile_creation():
    name = "John Doe"
    profile = "65-year-old male with type 2 diabetes on metformin. Needs medication review."

    tested = PatientProfile(name=name, profile=profile)

    assert tested.name == name
    assert tested.profile == profile


def test_to_json():
    name = "Jane Smith"
    profile = "45-year-old female with hypertension and asthma. Well-controlled on current medications."

    tested = PatientProfile(name=name, profile=profile)
    result = tested.to_json()
    expected = {
        "name": name,
        "profile": profile,
    }

    assert result == expected
    assert isinstance(result, dict)
    assert len(result) == 2


def test_load_from_json():
    data = {
        "name": "Bob Johnson",
        "profile": "30-year-old male, healthy, no current medications. Routine check-up.",
    }

    result = PatientProfile.load_from_json(data)
    expected = PatientProfile(name=data["name"], profile=data["profile"])

    assert result == expected
    assert isinstance(result, PatientProfile)


def test_round_trip_serialization():
    original = PatientProfile(
        name="Alice Brown",
        profile="55-year-old female with osteoarthritis. Takes ibuprofen as needed for joint pain.",
    )

    json_data = original.to_json()
    result = PatientProfile.load_from_json(json_data)

    assert result == original
    assert result.to_json() == original.to_json()


def test_json_serializable():
    tested = PatientProfile(
        name="Test Patient",
        profile="Test profile with medication history and current conditions.",
    )

    json_result = tested.to_json()

    # Should be JSON serializable
    json_str = json.dumps(json_result)
    parsed_back = json.loads(json_str)

    assert parsed_back == json_result
    assert PatientProfile.load_from_json(parsed_back) == tested


def test_empty_values():
    tested = PatientProfile(name="", profile="")

    assert tested.name == ""
    assert tested.profile == ""

    json_data = tested.to_json()
    assert json_data == {"name": "", "profile": ""}

    result = PatientProfile.load_from_json(json_data)
    assert result == tested


def test_long_profile():
    name = "Patient with Long History"
    profile = (
        "Complex 72-year-old patient with multiple comorbidities including "
        + "diabetes mellitus type 2, hypertension, chronic kidney disease stage 3, "
        + "and coronary artery disease. Current medications include metformin 1000mg "
        + "twice daily, lisinopril 20mg daily, atorvastatin 40mg at bedtime, and "
        + "aspirin 81mg daily. Requires careful monitoring of renal function and "
        + "medication dosing adjustments."
    )

    tested = PatientProfile(name=name, profile=profile)

    assert tested.name == name
    assert tested.profile == profile

    # Test serialization with long content
    json_data = tested.to_json()
    result = PatientProfile.load_from_json(json_data)
    assert result == tested
