from unittest.mock import patch, call

from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.medical_history import MedicalHistory
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> MedicalHistory:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return MedicalHistory(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = MedicalHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "medicalHistory"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = PastSurgicalHistoryCommand()
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the condition",
        "approximateStartDate": "YYYY-MM-DD",
        "approximateEndDate": "YYYY-MM-DD",
        "comments": "provided description of the patient specific history with the condition, as free text",
    }

    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any past condition. "
                "There can be only one condition per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(MedicalHistory, "condition_history")
def test_instruction_constraints(condition_history):
    def reset_mocks():
        condition_history.reset_mock()

    tested = helper_instance()

    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (conditions, "'MedicalHistory' cannot include: display1a, display2a, display3a."),
        ([], ""),
    ]
    for side_effect, expected in tests:
        condition_history.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert condition_history.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
