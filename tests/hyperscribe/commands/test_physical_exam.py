from unittest.mock import MagicMock

import pytest
from canvas_sdk.commands import PhysicalExamCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.commands.physical_exam import PhysicalExam
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> PhysicalExam:
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
    return PhysicalExam(settings, cache, identification)


def test_class():
    tested = PhysicalExam
    assert issubclass(tested, BaseQuestionnaire)


def test_schema_key():
    tested = PhysicalExam
    result = tested.schema_key()
    expected = "exam"
    assert result == expected


def test_command_from_json():
    chatter = MagicMock()
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        instruction = InstructionWithParameters(
            uuid="theUuid",
            instruction="theInstruction",
            information="theInformation",
            is_new=False,
            is_updated=True,
            audits=["theAudit"],
            parameters={'key': "value"},
        )
        _ = tested.command_from_json(instruction, chatter)
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.command_parameters()


def test_instruction_description():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.instruction_description()


def test_instruction_constraints():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.instruction_constraints()


def test_include_skipped():
    tested = helper_instance()
    result = tested.include_skipped()
    assert result is True


def test_sdk_command():
    tested = helper_instance()
    result = tested.sdk_command()
    expected = PhysicalExamCommand
    assert result == expected
