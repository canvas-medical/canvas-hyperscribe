from unittest.mock import MagicMock

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.commands.physical_exam import PhysicalExam
from hyperscribe.handlers.limited_cache import LimitedCache
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
    )
    cache = LimitedCache("patientUuid", {})
    return PhysicalExam(settings, cache, "patientUuid", "noteUuid", "providerUuid")


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
    result = tested.command_from_json(chatter, {})
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
