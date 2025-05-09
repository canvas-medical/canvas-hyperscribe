from unittest.mock import MagicMock

import pytest
from canvas_sdk.commands import ReviewOfSystemsCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.review_of_system import ReviewOfSystem
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> ReviewOfSystem:
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
    return ReviewOfSystem(settings, cache, identification)


def test_class():
    tested = ReviewOfSystem
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ReviewOfSystem
    result = tested.schema_key()
    expected = "ros"
    assert result == expected


def test_staged_command_extract():
    tested = ReviewOfSystem
    tests = [
        ({}, None),
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
    with pytest.raises(NotImplementedError):
        instruction = InstructionWithParameters(
            uuid="theUuid",
            index=7,
            instruction="theInstruction",
            information="theInformation",
            is_new=False,
            is_updated=True,
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
    expected = ReviewOfSystemsCommand
    assert result == expected
