import json

from evaluations.structures.chart import Chart


def test_chart_creation():
    chart_data = {
        "demographicStr": "65-year-old male",
        "conditionHistory": "Hypertension, diabetes",
        "currentAllergies": "Penicillin",
        "currentConditions": "Type 2 diabetes",
        "currentMedications": "Metformin 500mg",
        "currentGoals": "HbA1c < 7%",
        "familyHistory": "Family history of diabetes",
        "surgeryHistory": "None",
    }

    tested = Chart(**chart_data)

    assert tested.demographicStr == "65-year-old male"
    assert tested.conditionHistory == "Hypertension, diabetes"
    assert tested.currentAllergies == "Penicillin"
    assert tested.currentConditions == "Type 2 diabetes"
    assert tested.currentMedications == "Metformin 500mg"
    assert tested.currentGoals == "HbA1c < 7%"
    assert tested.familyHistory == "Family history of diabetes"
    assert tested.surgeryHistory == "None"


def test_to_json():
    chart_data = {
        "demographicStr": "45-year-old female",
        "conditionHistory": "Asthma",
        "currentAllergies": "None known",
        "currentConditions": "Mild asthma",
        "currentMedications": "Albuterol inhaler",
        "currentGoals": "Control symptoms",
        "familyHistory": "No significant family history",
        "surgeryHistory": "Appendectomy 2010",
    }

    tested = Chart(**chart_data)
    result = tested.to_json()
    expected = chart_data

    assert result == expected
    assert isinstance(result, dict)
    assert len(result) == 8


def test_load_from_json():
    chart_data = {
        "demographicStr": "30-year-old male",
        "conditionHistory": "Healthy",
        "currentAllergies": "Shellfish",
        "currentConditions": "None",
        "currentMedications": "None",
        "currentGoals": "Maintain health",
        "familyHistory": "Heart disease",
        "surgeryHistory": "None",
    }

    result = Chart.load_from_json(chart_data)
    expected = Chart(**chart_data)

    assert result == expected
    assert isinstance(result, Chart)


def test_round_trip_serialization():
    original_data = {
        "demographicStr": "55-year-old female",
        "conditionHistory": "Hypertension, hyperlipidemia",
        "currentAllergies": "Latex, iodine",
        "currentConditions": "Well-controlled hypertension",
        "currentMedications": "Lisinopril 10mg daily, atorvastatin 20mg",
        "currentGoals": "BP < 130/80, LDL < 100",
        "familyHistory": "Mother with stroke at 70",
        "surgeryHistory": "Cholecystectomy 2015",
    }

    tested = Chart(**original_data)
    json_data = tested.to_json()
    result = Chart.load_from_json(json_data)

    assert result == tested
    assert result.to_json() == original_data


def test_json_serializable():
    chart_data = {
        "demographicStr": "Test patient",
        "conditionHistory": "Test condition",
        "currentAllergies": "Test allergy",
        "currentConditions": "Test current condition",
        "currentMedications": "Test medication",
        "currentGoals": "Test goal",
        "familyHistory": "Test family history",
        "surgeryHistory": "Test surgery",
    }

    tested = Chart(**chart_data)
    json_result = tested.to_json()

    # Should be JSON serializable
    json_str = json.dumps(json_result)
    parsed_back = json.loads(json_str)

    assert parsed_back == json_result
    assert Chart.load_from_json(parsed_back) == tested
