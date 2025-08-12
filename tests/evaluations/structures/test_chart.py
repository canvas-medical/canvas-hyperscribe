import pytest
from evaluations.structures.chart import Chart
from hyperscribe.structures.coded_item import CodedItem
from tests.helper import is_namedtuple


def test_class():
    tested = Chart
    fields = {
        "demographic_str": str,
        "condition_history": list[CodedItem],
        "current_allergies": list[CodedItem],
        "current_conditions": list[CodedItem],
        "current_medications": list[CodedItem],
        "current_goals": list[CodedItem],
        "family_history": list[CodedItem],
        "surgery_history": list[CodedItem],
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            Chart(
                demographic_str="45-year-old female",
                condition_history=[
                    CodedItem(uuid="uuid-1", label="Personal history of nicotine dependence", code="Z87.891")
                ],
                current_allergies=[CodedItem(uuid="uuid-2", label="Allergy to penicillin", code="Z88.1")],
                current_conditions=[CodedItem(uuid="uuid-3", label="Asthma, unspecified", code="J45.9")],
                current_medications=[
                    CodedItem(uuid="uuid-4", label="Albuterol 90 mcg/dose metered dose inhaler", code="329498")
                ],
                current_goals=[CodedItem(uuid="uuid-5", label="Control asthma symptoms", code="")],
                family_history=[],
                surgery_history=[
                    CodedItem(uuid="uuid-6", label="Resection of appendix, open approach", code="0DT70ZZ")
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
                condition_history=[CodedItem(uuid="uuid-1", label="Personal history of tobacco use", code="Z87.891")],
                current_allergies=[CodedItem(uuid="uuid-2", label="Allergy to seafood", code="Z91.013")],
                current_conditions=[],
                current_medications=[CodedItem(uuid="uuid-3", label="Multivitamin", code="860975")],
                current_goals=[CodedItem(uuid="uuid-4", label="Maintain health", code="")],
                family_history=[
                    CodedItem(uuid="uuid-5", label="Family history of ischemic heart disease", code="Z82.49")
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
