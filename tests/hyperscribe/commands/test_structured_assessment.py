from unittest.mock import MagicMock

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.commands.structured_assessment import StructuredAssessment
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> StructuredAssessment:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return StructuredAssessment(settings, cache, identification)


def test_class():
    tested = StructuredAssessment
    assert issubclass(tested, BaseQuestionnaire)


def test_schema_key():
    tested = StructuredAssessment
    result = tested.schema_key()
    expected = "structuredAssessment"
    assert result == expected


def test_command_from_json():
    chatter = MagicMock()
    tested = helper_instance()
    instruction = InstructionWithParameters(
        uuid="theUuid",
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        audits=["theAudit"],
        parameters={'key': "value"},
    )
    result = tested.command_from_json(instruction, chatter)
    assert result is None
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {}
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ""
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
