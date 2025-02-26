import pytest

from commander.protocols.commands.base import Base
from commander.protocols.limited_cache import LimitedCache
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Base:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return Base(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test___init__():
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    tested = Base(settings, cache, "patientUuid", "noteUuid", "providerUuid")
    assert tested.settings == settings
    assert tested.patient_uuid == "patientUuid"
    assert tested.note_uuid == "noteUuid"
    assert tested.provider_uuid == "providerUuid"
    assert tested.cache == cache


def test_class_name():
    tested = Base
    result = tested.class_name()
    expected = "Base"
    assert result == expected


def test_schema_key():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.schema_key()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_staged_command_extract():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.staged_command_extract({})
    expected = "NotImplementedError"
    assert e.typename == expected


def test_command_from_json():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.command_from_json({})
    expected = "NotImplementedError"
    assert e.typename == expected


def test_command_parameters():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.command_parameters()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_instruction_description():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.instruction_description()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_instruction_constraints():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.instruction_constraints()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_is_available():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.is_available()
    expected = "NotImplementedError"
    assert e.typename == expected
