import json
from hashlib import md5
from unittest.mock import MagicMock

from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.plan import Plan
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(custom_prompts: list[CustomPrompt] = []) -> Plan:
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
    return Plan(settings, cache, identification)


def test_class():
    tested = Plan
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Plan
    result = tested.schema_key()
    expected = "plan"
    assert result == expected


def test_note_section():
    tested = Plan
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = Plan
    tests = [
        ({}, None),
        ({"narrative": "theNarrative"}, CodedItem(label="theNarrative", code="", uuid="")),
        ({"narrative": ""}, None),
    ]
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
        "parameters": {"plan": "thePlan"},
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = PlanCommand(narrative="thePlan", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "plan": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    result = tested.command_parameters_schemas()
    expected = "76c204ad9f47889a6e55d7fe0870f227"
    assert md5(json.dumps(result).encode()).hexdigest() == expected


def test_instruction_description():
    # without custom prompt
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Overall treatment plan and care strategy discussed during the visit, including ongoing management, "
        "monitoring approaches, medication strategies, lifestyle modifications, and follow-up scheduling. "
        "This captures the provider's overall approach to the patient's care. "
        "There can be only one plan per instruction, and no instruction if no plan of care is discussed."
    )
    assert result == expected
    #
    # with custom prompt
    tested = helper_instance(custom_prompts=[CustomPrompt(command="Plan", prompt="custom prompt text")])
    result = tested.instruction_description()
    expected = (
        "Overall treatment plan and care strategy discussed during the visit, including ongoing management, "
        "monitoring approaches, medication strategies, lifestyle modifications, and follow-up scheduling. "
        "This captures the provider's overall approach to the patient's care. "
        "There can be only one plan per instruction, and no instruction if no plan of care is discussed. "
        "For documentation purposes, always include the relevant parts of the transcript for reference."
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
