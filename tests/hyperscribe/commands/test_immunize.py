from hashlib import md5
import json
from unittest.mock import MagicMock

from canvas_sdk.commands.commands.instruct import InstructCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.immunize import Immunize
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Immunize:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
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
    return Immunize(settings, cache, identification)


def test_class():
    tested = Immunize
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Immunize
    result = tested.schema_key()
    expected = "immunize"
    assert result == expected


def test_note_section():
    tested = Immunize
    result = tested.note_section()
    expected = "Procedures"
    assert result == expected


def test_staged_command_extract():
    tested = Immunize
    tests = [
        ({}, None),
        (
            {"coding": {"text": "theImmunization"}, "manufacturer": "theManufacturer", "sig_original": "theSig"},
            CodedItem(label="theImmunization: theSig (theManufacturer)", code="", uuid=""),
        ),
        (
            {"coding": {"text": "theImmunization"}, "manufacturer": "", "sig_original": "theSig"},
            CodedItem(label="theImmunization: theSig (n/a)", code="", uuid=""),
        ),
        (
            {"coding": {"text": "theImmunization"}, "manufacturer": "theManufacturer", "sig_original": ""},
            CodedItem(label="theImmunization: n/a (theManufacturer)", code="", uuid=""),
        ),
        ({"coding": {"text": ""}, "manufacturer": "theManufacturer", "sig_original": "theSig"}, None),
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
        "parameters": {"immunize": "theImmunization", "sig": "theSig"},
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = InstructCommand(
        instruction="Advice to read information",
        comment="theSig - theImmunization",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "immunize": "",
        "sig": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "7ed6df86c41bd6f4a707e03b939d92ed"
    assert schema_hash == expected_hash

    tests = [
        (
            [{"immunize": "Flu vaccine (CPT 90658)", "sig": "Administer 0.5ml IM"}],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {"immunize": "Flu vaccine (CPT 90658)", "sig": "Administer 0.5ml IM"},
                {"immunize": "Tetanus vaccine (CPT 90703)", "sig": "Administer 0.5ml IM"},
            ],
            "[{'immunize': 'Flu vaccine (CPT 90658)', 'sig': 'Administer 0.5ml IM'}, "
            "{'immunize': 'Tetanus vaccine (CPT 90703)', 'sig': 'Administer 0.5ml IM'}] is too long",
        ),
        (
            [{"immunize": "Flu vaccine (CPT 90658)", "sig": "Administer 0.5ml IM", "extra": "field"}],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [{"sig": "Administer 0.5ml IM"}],
            "'immunize' is a required property, in path [0]",
        ),
        (
            [{"immunize": "Flu vaccine (CPT 90658)"}],
            "'sig' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Immunization or vaccine to be administered. "
        "There can be only one immunization per instruction, and no instruction in the lack of."
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
    assert result is False
