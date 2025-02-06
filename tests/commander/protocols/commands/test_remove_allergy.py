from unittest.mock import patch, call

from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.remove_allergy import RemoveAllergy
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> RemoveAllergy:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return RemoveAllergy(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = RemoveAllergy
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "removeAllergy"
    assert result == expected


@patch.object(RemoveAllergy, "current_allergies")
def test_command_from_json(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()
    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (1, "theUuid2", [call(), call()]),
        (2, "theUuid3", [call(), call()]),
        (4, "", [call()]),
    ]
    for idx, exp_uuid, calls in tests:
        current_allergies.side_effect = [allergies, allergies]
        params = {
            'allergies': 'display2a',
            'allergyIndex': idx,
            'narrative': 'theNarrative',
        }
        result = tested.command_from_json(params)
        expected = RemoveAllergyCommand(
            allergy_id=exp_uuid,
            narrative="theNarrative",
            note_uuid="noteUuid",
        )
        assert result == expected
        assert current_allergies.mock_calls == calls
        reset_mocks()


@patch.object(RemoveAllergy, "current_allergies")
def test_command_parameters(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()
    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_allergies.side_effect = [allergies]
    result = tested.command_parameters()
    expected = {
        'allergies': 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        "allergyIndex": "Index of the allergy to remove, as integer",
        "narrative": "explanation of why the allergy is removed, as free text",
    }
    assert result == expected
    calls = [call()]
    assert current_allergies.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Remove a previously diagnosed allergy. "
                "There can be only one allergy, with the explanation, to remove per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(RemoveAllergy, "current_allergies")
def test_instruction_constraints(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()
    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_allergies.side_effect = [allergies]
    result = tested.instruction_constraints()
    expected = ("'RemoveAllergy' has to be related to one of the following allergies: "
                "display1a, display2a, display3a.")
    assert result == expected
    calls = [call()]
    assert current_allergies.mock_calls == calls
    reset_mocks()


@patch.object(RemoveAllergy, "current_allergies")
def test_is_available(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()
    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (allergies, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_allergies.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_allergies.mock_calls == calls
        reset_mocks()
