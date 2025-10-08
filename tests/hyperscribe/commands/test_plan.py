from unittest.mock import MagicMock

from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.plan import Plan
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Plan:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
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
        "plan": "detailed description of the treatment plan in free text, including specific medications, doses, "
        "follow-up dates/times, alternative options discussed, contingency plans, and ongoing interventions"
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Comprehensive treatment plan capturing all agreed-upon actions and future care decisions. "
        "Include: (1) medication changes (specific doses, timing, formulations), (2) exact follow-up schedule "
        "(specific dates/times if discussed, not just timeframes like 'a couple months'), (3) alternative treatment "
        "options mentioned for future consideration, (4) contingency plans (e.g., 'contact sooner if symptoms worsen'), "
        "(5) ongoing interventions (therapy, monitoring, lifestyle modifications), and (6) important patient-specific "
        "considerations discussed that may impact treatment (e.g., pregnancy planning, long-term medication concerns). "
        "Capture specific details from the conversation rather than generic summaries. "
        "There can be only one plan per instruction, and no instruction in the lack of."
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
