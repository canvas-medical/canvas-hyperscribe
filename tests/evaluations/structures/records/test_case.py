from evaluations.structures.enums.case_status import CaseStatus
from evaluations.structures.records.case import Case
from evaluations.structures.chart import Chart
from hyperscribe.structures.line import Line
from tests.helper import is_namedtuple


def test_class():
    tested = Case
    fields = {
        "name": str,
        "transcript": dict[str, list[Line]],
        "limited_chart": Chart,
        "profile": str,
        "validation_status": CaseStatus,
        "batch_identifier": str,
        "tags": dict,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = Case(name="theName")
    assert result.name == "theName"
    assert result.transcript == {}
    assert result.limited_chart == Chart(
        demographic_str="",
        condition_history=[],
        current_allergies=[],
        current_conditions=[],
        current_medications=[],
        current_goals=[],
        family_history=[],
        surgery_history=[],
    )
    assert result.profile == ""
    assert result.validation_status == CaseStatus.GENERATION
    assert result.batch_identifier == ""
    assert result.tags == {}
    assert result.id == 0


def test_load_record():
    tested = Case
    result = tested.load_record(
        {
            "name": "theName",
            "transcript": {
                "cycle_001": [
                    {"speaker": "theSpeaker1", "text": "theText1"},
                    {"speaker": "theSpeaker2", "text": "theText2"},
                    {},
                ],
                "cycle_002": [{"speaker": "theSpeaker3", "text": "theText3"}],
            },
            "limited_chart": {
                "demographicStr": "Sample demographic",
                "conditionHistory": [],
                "currentAllergies": [],
                "currentConditions": [],
                "currentMedications": [],
                "currentGoals": [],
                "familyHistory": [],
                "surgeryHistory": [],
            },
            "profile": "theProfile",
            "validation_status": "evaluation",
            "batch_identifier": "theBatchIdentifier",
            "tags": {"tag1": "tag1", "tag2": "tag2"},
            "id": 147,
        },
    )
    expected = Case(
        name="theName",
        transcript={
            "cycle_001": [
                Line(speaker="theSpeaker1", text="theText1"),
                Line(speaker="theSpeaker2", text="theText2"),
                Line(speaker="", text=""),
            ],
            "cycle_002": [Line(speaker="theSpeaker3", text="theText3")],
        },
        limited_chart=Chart(
            demographic_str="Sample demographic",
            condition_history=[],
            current_allergies=[],
            current_conditions=[],
            current_medications=[],
            current_goals=[],
            family_history=[],
            surgery_history=[],
        ),
        profile="theProfile",
        validation_status=CaseStatus.EVALUATION,
        batch_identifier="theBatchIdentifier",
        tags={"tag1": "tag1", "tag2": "tag2"},
        id=147,
    )
    assert result == expected
