from unittest.mock import patch, call

from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.medication import Medication
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> Medication:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Medication(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Medication
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "medicationStatement"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = MedicationStatementCommand()
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the taken medication",
        "sig": "directions, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Current medication. "
                "There can be only one medication per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(Medication, "current_medications")
def test_instruction_constraints(current_medications):
    def reset_mocks():
        current_medications.reset_mock()

    tested = helper_instance()

    medications = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (medications, "'Medication' cannot include: display1a, display2a, display3a."),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_medications.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_medications.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
