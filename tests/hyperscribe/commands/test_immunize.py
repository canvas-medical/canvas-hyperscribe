from unittest.mock import MagicMock

from canvas_sdk.commands.commands.instruct import InstructCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.immunize import Immunize
from hyperscribe.handlers.limited_cache import LimitedCache
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
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
    )
    cache = LimitedCache("patientUuid", {})
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


def test_staged_command_extract():
    tested = Immunize
    tests = [
        ({}, None),
        ({
             "coding": {"text": "theImmunization"},
             "manufacturer": "theManufacturer",
             "sig_original": "theSig",
         }, CodedItem(label="theImmunization: theSig (theManufacturer)", code="", uuid="")),
        ({
             "coding": {"text": "theImmunization"},
             "manufacturer": "",
             "sig_original": "theSig",
         }, CodedItem(label="theImmunization: theSig (n/a)", code="", uuid="")),
        ({
             "coding": {"text": "theImmunization"},
             "manufacturer": "theManufacturer",
             "sig_original": "",
         }, CodedItem(label="theImmunization: n/a (theManufacturer)", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "manufacturer": "theManufacturer",
             "sig_original": "theSig",
         }, None),
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
        "is_updated": True,        "parameters": {
            "immunize": "theImmunization",
            "sig": "theSig",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = InstructCommand(
        instruction="Advice to read information",
        comment='theSig - theImmunization',
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "immunize": "medical name of the immunization and its CPT code",
        "sig": "directions, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Immunization or vaccine to be administered. "
                "There can be only one immunization per instruction, and no instruction in the lack of.")
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
