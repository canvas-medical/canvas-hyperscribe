from unittest.mock import patch, call

from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.prescription import Prescription
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> Prescription:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Prescription(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Prescription
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "prescribe"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = PrescribeCommand()
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {}
    assert result == expected


@patch.object(Prescription, "current_conditions")
def test_command_parameters(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()

    medications = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (medications, {
            "keywords": "comma separated keywords of up to 5 synonyms of the medication to prescribe",
            "sig": "directions, as free text",
            "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following the standard practices, as integer",
            "substitution": "one of: allowed/not_allowed",
            "comment": "rational of the prescription, as free text",
            "condition": "None or, one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)",
            "conditionIndex": "index of the condition for which the medication is prescribed, as integer or -1 if the prescription is not related to any listed condition",
        }),
        ([], {
            "keywords": "comma separated keywords of up to 5 synonyms of the medication to prescribe",
            "sig": "directions, as free text",
            "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following the standard practices, as integer",
            "substitution": "one of: allowed/not_allowed",
            "comment": "rational of the prescription, as free text",
        }),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.command_parameters()
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Medication prescription, including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one prescription per instruction, and no instruction in the lack of.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
