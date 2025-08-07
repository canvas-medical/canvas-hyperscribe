import pytest
from evaluations.structures.chart import Chart
from evaluations.structures.chart_item import ChartItem
from tests.helper import is_namedtuple


def test_class():
    tested = Chart
    fields = {
        "demographic_str": str,
        "condition_history": list[ChartItem],
        "current_allergies": list[ChartItem],
        "current_conditions": list[ChartItem],
        "current_medications": list[ChartItem],
        "current_goals": list[ChartItem],
        "family_history": list[ChartItem],
        "surgery_history": list[ChartItem],
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            Chart(
                demographic_str="45-year-old female",
                condition_history=[
                    ChartItem(code="Z87.891", label="Personal history of nicotine dependence", uuid="uuid-1")
                ],
                current_allergies=[ChartItem(code="Z88.1", label="Allergy to penicillin", uuid="uuid-2")],
                current_conditions=[ChartItem(code="J45.9", label="Asthma, unspecified", uuid="uuid-3")],
                current_medications=[
                    ChartItem(code="329498", label="Albuterol 90 mcg/dose metered dose inhaler", uuid="uuid-4")
                ],
                current_goals=[ChartItem(code="", label="Control asthma symptoms", uuid="uuid-5")],
                family_history=[],
                surgery_history=[
                    ChartItem(code="0DT70ZZ", label="Resection of appendix, open approach", uuid="uuid-6")
                ],
            ),
            {
                "demographicStr": "45-year-old female",
                "conditionHistory": [
                    {"code": "Z87.891", "label": "Personal history of nicotine dependence", "uuid": "uuid-1"}
                ],
                "currentAllergies": [{"code": "Z88.1", "label": "Allergy to penicillin", "uuid": "uuid-2"}],
                "currentConditions": [{"code": "J45.9", "label": "Asthma, unspecified", "uuid": "uuid-3"}],
                "currentMedications": [
                    {"code": "329498", "label": "Albuterol 90 mcg/dose metered dose inhaler", "uuid": "uuid-4"}
                ],
                "currentGoals": [{"code": "", "label": "Control asthma symptoms", "uuid": "uuid-5"}],
                "familyHistory": [],
                "surgeryHistory": [
                    {"code": "0DT70ZZ", "label": "Resection of appendix, open approach", "uuid": "uuid-6"}
                ],
            },
        ),
        (
            Chart(
                demographic_str="",
                condition_history=[],
                current_allergies=[],
                current_conditions=[],
                current_medications=[],
                current_goals=[],
                family_history=[],
                surgery_history=[],
            ),
            {
                "demographicStr": "",
                "conditionHistory": [],
                "currentAllergies": [],
                "currentConditions": [],
                "currentMedications": [],
                "currentGoals": [],
                "familyHistory": [],
                "surgeryHistory": [],
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
                "conditionHistory": [{"code": "Z87.891", "label": "Personal history of tobacco use", "uuid": "uuid-1"}],
                "currentAllergies": [{"code": "Z91.013", "label": "Allergy to seafood", "uuid": "uuid-2"}],
                "currentConditions": [],
                "currentMedications": [{"code": "860975", "label": "Multivitamin", "uuid": "uuid-3"}],
                "currentGoals": [{"code": "", "label": "Maintain health", "uuid": "uuid-4"}],
                "familyHistory": [
                    {"code": "Z82.49", "label": "Family history of ischemic heart disease", "uuid": "uuid-5"}
                ],
                "surgeryHistory": [],
            },
            Chart(
                demographic_str="30-year-old male",
                condition_history=[ChartItem(code="Z87.891", label="Personal history of tobacco use", uuid="uuid-1")],
                current_allergies=[ChartItem(code="Z91.013", label="Allergy to seafood", uuid="uuid-2")],
                current_conditions=[],
                current_medications=[ChartItem(code="860975", label="Multivitamin", uuid="uuid-3")],
                current_goals=[ChartItem(code="", label="Maintain health", uuid="uuid-4")],
                family_history=[
                    ChartItem(code="Z82.49", label="Family history of ischemic heart disease", uuid="uuid-5")
                ],
                surgery_history=[],
            ),
        ),
        (
            {
                "wrongKey": "Invalid key",
                "conditionHistory": [],
                "currentAllergies": [],
                "currentConditions": [],
                "currentMedications": [],
                "currentGoals": [],
                "familyHistory": [],
                "surgeryHistory": [],
            },
            KeyError,
        ),
    ]

    for data, expected in tests:
        if expected == KeyError:
            with pytest.raises(KeyError):
                Chart.load_from_json(data)
        else:
            result = Chart.load_from_json(data)
            assert result == expected
