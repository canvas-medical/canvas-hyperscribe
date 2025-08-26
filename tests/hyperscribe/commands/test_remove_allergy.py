from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.remove_allergy import RemoveAllergy
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> RemoveAllergy:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return RemoveAllergy(settings, cache, identification)


def test_class():
    tested = RemoveAllergy
    assert issubclass(tested, Base)


def test_schema_key():
    tested = RemoveAllergy
    result = tested.schema_key()
    expected = "removeAllergy"
    assert result == expected


def test_staged_command_extract():
    tested = RemoveAllergy
    tests = [
        ({}, None),
        (
            {"allergy": {"text": "theAllergy"}, "narrative": "theNarrative"},
            CodedItem(label="theAllergy: theNarrative", code="", uuid=""),
        ),
        ({"allergy": {"text": ""}, "narrative": "theNarrative"}, None),
        ({"allergy": {"text": "theAllergy"}, "narrative": ""}, CodedItem(label="theAllergy: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "current_allergies")
@patch.object(RemoveAllergy, "add_code2description")
def test_command_from_json(add_code2description, current_allergies):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        current_allergies.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()
    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (1, "theUuid2", [call("theUuid2", "display2a")]),
        (2, "theUuid3", [call("theUuid3", "display3a")]),
        (4, "", []),
    ]
    for idx, exp_uuid, exp_calls in tests:
        current_allergies.side_effect = [allergies, allergies]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {"allergies": "display2a", "allergyIndex": idx, "narrative": "theNarrative"},
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = RemoveAllergyCommand(allergy_id=exp_uuid, narrative="theNarrative", note_uuid="noteUuid")
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_allergies.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "current_allergies")
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
        "allergies": "one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)",
        "allergyIndex": "Index of the allergy to remove, or -1, as integer",
        "narrative": "explanation of why the allergy is removed, as free text",
    }
    assert result == expected
    calls = [call()]
    assert current_allergies.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Remove a previously diagnosed allergy. "
        "There can be only one allergy, with the explanation, to remove per instruction, "
        "and no instruction in the lack of."
    )
    assert result == expected


@patch.object(LimitedCache, "current_allergies")
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
    expected = "'RemoveAllergy' has to be related to one of the following allergies: display1a, display2a, display3a."
    assert result == expected
    calls = [call()]
    assert current_allergies.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_allergies")
def test_is_available(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()
    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [(allergies, True), ([], False)]
    for side_effect, expected in tests:
        current_allergies.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_allergies.mock_calls == calls
        reset_mocks()
