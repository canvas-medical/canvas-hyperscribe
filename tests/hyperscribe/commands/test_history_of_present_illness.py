from hashlib import md5
import json
from unittest.mock import MagicMock

from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(custom_prompts: list[CustomPrompt] = None) -> HistoryOfPresentIllness:
    if custom_prompts is None:
        custom_prompts = []
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=custom_prompts,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return HistoryOfPresentIllness(settings, cache, identification)


def test_class():
    tested = HistoryOfPresentIllness
    assert issubclass(tested, Base)


def test_schema_key():
    tested = HistoryOfPresentIllness
    result = tested.schema_key()
    expected = "hpi"
    assert result == expected


def test_note_section():
    tested = HistoryOfPresentIllness
    result = tested.note_section()
    expected = "Subjective"
    assert result == expected


def test_staged_command_extract():
    tested = HistoryOfPresentIllness
    tests = [({}, None), ({"narrative": "theNarrative"}, CodedItem(label="theNarrative", code="", uuid=""))]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


def test_command_from_json():
    chatter = MagicMock()
    tested = helper_instance()
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {"narrative": "theNarrative"},
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = HistoryOfPresentIllnessCommand(narrative="theNarrative", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "narrative": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "f74d047438c7bb480f347e81e8e479e5"
    assert schema_hash == expected_hash

    tests = [
        (
            [{"narrative": "Patient presents with chest pain that started 2 hours ago"}],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {"narrative": "Patient has chest pain"},
                {"narrative": "Patient has shortness of breath"},
            ],
            "[{'narrative': 'Patient has chest pain'}, {'narrative': 'Patient has shortness of breath'}] is too long",
        ),
        (
            [{"narrative": "Patient has chest pain", "extra": "field"}],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [{}],
            "'narrative' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    # without custom prompt
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Highlights of the patient's symptoms and surrounding events and observations. "
        "There can be multiple highlights within an instruction, but only one such instruction in the "
        "whole discussion. "
        "So, if one was already found, simply update it by intelligently merging all key highlights."
    )
    assert result == expected
    #
    # with custom prompt
    tested = helper_instance(
        custom_prompts=[
            CustomPrompt(
                command="HistoryOfPresentIllness",
                prompt="custom prompt text",
            )
        ]
    )
    result = tested.instruction_description()
    expected = (
        "Highlights of the patient's symptoms and surrounding events and observations. "
        "There can be multiple highlights within an instruction, but only one such instruction in the "
        "whole discussion. "
        "So, if one was already found, simply update it by intelligently merging all key highlights. "
        "For documentation purposes, always include the relevant parts of the transcript for reference, "
        "including any previous sections when merging."
    )
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
