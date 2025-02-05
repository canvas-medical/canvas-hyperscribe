from unittest.mock import patch, call

from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.update_diagnose import UpdateDiagnose
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> UpdateDiagnose:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return UpdateDiagnose(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = UpdateDiagnose
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "updateDiagnosis"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = DiagnoseCommand()
    assert result == expected


@patch.object(UpdateDiagnose, "current_conditions")
def test_command_parameters(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the new diagnosed condition",
        "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the new diagnosed condition",
        "previousCondition": 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        "previousConditionIndex": "index of the previous Condition, as integer",
        "rationale": "rationale about the current assessment, as free text",
        "assessment": "today's assessment of the new condition, as free text",
    }
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(UpdateDiagnose, "current_conditions")
def test_instruction_description(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_description()
    expected = ("Change of a medical condition (display1a, display2a, display3a) identified by the provider, "
                "including rationale, current assessment. "
                "There is one instruction per condition change, and no instruction in the lack of.")
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(UpdateDiagnose, "current_conditions")
def test_instruction_constraints(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_constraints()
    expected = ("'UpdateDiagnose' has to be an update from one of the following conditions: "
                "display1a (ICD-10: CODE12.3), "
                "display2a (ICD-10: CODE45), "
                "display3a (ICD-10: CODE98.76)")
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(UpdateDiagnose, "current_conditions")
def test_is_available(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (conditions, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()
