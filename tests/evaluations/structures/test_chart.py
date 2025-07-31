from evaluations.structures.chart import Chart
from tests.helper import is_namedtuple


def test_class():
    tested = Chart
    fields = {
        "demographic_str": str,
        "condition_history": str,
        "current_allergies": str,
        "current_conditions": str,
        "current_medications": str,
        "current_goals": str,
        "family_history": str,
        "surgery_history": str,
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            Chart(
                demographic_str="45-year-old female",
                condition_history="Asthma",
                current_allergies="None known",
                current_conditions="Mild asthma",
                current_medications="Albuterol inhaler",
                current_goals="Control symptoms",
                family_history="No significant family history",
                surgery_history="Appendectomy 2010",
            ),
            {
                "demographicStr": "45-year-old female",
                "conditionHistory": "Asthma",
                "currentAllergies": "None known",
                "currentConditions": "Mild asthma",
                "currentMedications": "Albuterol inhaler",
                "currentGoals": "Control symptoms",
                "familyHistory": "No significant family history",
                "surgeryHistory": "Appendectomy 2010",
            },
        ),
        (
            Chart(
                demographic_str="",
                condition_history="",
                current_allergies="",
                current_conditions="",
                current_medications="",
                current_goals="",
                family_history="",
                surgery_history="",
            ),
            {
                "demographicStr": "",
                "conditionHistory": "",
                "currentAllergies": "",
                "currentConditions": "",
                "currentMedications": "",
                "currentGoals": "",
                "familyHistory": "",
                "surgeryHistory": "",
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
                "demographicStr": "30-year-old male",
                "conditionHistory": "Healthy",
                "currentAllergies": "Shellfish",
                "currentConditions": "None",
                "currentMedications": "None",
                "currentGoals": "Maintain health",
                "familyHistory": "Heart disease",
                "surgeryHistory": "None",
            },
            Chart(
                demographic_str="30-year-old male",
                condition_history="Healthy",
                current_allergies="Shellfish",
                current_conditions="None",
                current_medications="None",
                current_goals="Maintain health",
                family_history="Heart disease",
                surgery_history="None",
            ),
        ),
        (
            {
                "demographicStr": "Test patient",
                "conditionHistory": "Test condition",
                "currentAllergies": "Test allergy",
                "currentConditions": "Test current condition",
                "currentMedications": "Test medication",
                "currentGoals": "Test goal",
                "familyHistory": "Test family history",
                "surgeryHistory": "Test surgery",
            },
            Chart(
                demographic_str="Test patient",
                condition_history="Test condition",
                current_allergies="Test allergy",
                current_conditions="Test current condition",
                current_medications="Test medication",
                current_goals="Test goal",
                family_history="Test family history",
                surgery_history="Test surgery",
            ),
        ),
    ]

    for data, expected in tests:
        result = Chart.load_from_json(data)
        assert result == expected