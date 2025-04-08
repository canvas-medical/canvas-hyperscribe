from unittest.mock import MagicMock, patch, call

import pytest
from canvas_sdk.v1.data import PracticeLocation, PracticeLocationSetting, Staff

from hyperscribe.commands.base import Base
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


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
    with pytest.raises(NotImplementedError):
        _ = tested.schema_key()


def test_staged_command_extract():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.staged_command_extract({})


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


def test_is_available():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.is_available()


@patch.object(PracticeLocation, 'settings')
@patch.object(PracticeLocation, 'objects')
@patch.object(Staff, 'objects')
def test_practice_setting(staff_db, practice_location_db, practice_settings_db):
    def reset_mocks():
        staff_db.reset_mock()
        practice_location_db.reset_mock()
        practice_settings_db.reset_mock()

    tested = helper_instance()

    # all good
    # -- provider has no primary practice
    staff_db.get.side_effect = [Staff(primary_practice_location=None)]
    practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [PracticeLocationSetting(value="theValue")]

    result = tested.practice_setting("theSetting")
    expected = "theValue"
    assert result == expected

    calls = [call.get(id='providerUuid')]
    assert staff_db.mock_calls == calls
    calls = [
        call.order_by('dbid'),
        call.order_by().first(),
    ]
    assert practice_location_db.mock_calls == calls
    calls = [
        call.filter(name='theSetting'),
        call.filter().order_by('dbid'),
        call.filter().order_by().first(),
    ]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()
    # -- provider has one primary practice
    staff_db.get.side_effect = [Staff(primary_practice_location=PracticeLocation(full_name="theLocation"))]
    practice_location_db.order_by.return_value.first.side_effect = []
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [PracticeLocationSetting(value="theValue")]

    result = tested.practice_setting("theSetting")
    expected = "theValue"
    assert result == expected

    calls = [call.get(id='providerUuid')]
    assert staff_db.mock_calls == calls
    assert practice_location_db.mock_calls == []
    calls = [
        call.filter(name='theSetting'),
        call.filter().order_by('dbid'),
        call.filter().order_by().first(),
    ]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()

    # no setting found
    staff_db.get.side_effect = [Staff(primary_practice_location=None)]
    practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [None]

    result = tested.practice_setting("theSetting")
    assert result is None

    calls = [call.get(id='providerUuid')]
    assert staff_db.mock_calls == calls
    calls = [
        call.order_by('dbid'),
        call.order_by().first(),
    ]
    assert practice_location_db.mock_calls == calls
    calls = [
        call.filter(name='theSetting'),
        call.filter().order_by('dbid'),
        call.filter().order_by().first(),
    ]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()

    # no practice found
    staff_db.get.side_effect = [Staff(primary_practice_location=None)]
    practice_location_db.order_by.return_value.first.side_effect = [None]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = []

    result = tested.practice_setting("theSetting")
    assert result is None

    calls = [call.get(id='providerUuid')]
    assert staff_db.mock_calls == calls
    calls = [
        call.order_by('dbid'),
        call.order_by().first(),
    ]
    assert practice_location_db.mock_calls == calls
    assert practice_settings_db.mock_calls == []
    reset_mocks()
