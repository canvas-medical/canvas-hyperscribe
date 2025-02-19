from datetime import date
from unittest.mock import patch, call

from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.diagnose import Diagnose
from commander.protocols.selector_chat import SelectorChat
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Diagnose:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Diagnose(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Diagnose
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "diagnose"
    assert result == expected


@patch.object(SelectorChat, "condition_from")
def test_command_from_json(condition_from):
    def reset_mocks():
        condition_from.reset_mock()

    tested = helper_instance()
    condition_from.side_effect = [CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3")]
    parameters = {
        "keywords": "keyword1,keyword2,keyword3",
        "ICD10": "ICD01,ICD02,ICD03",
        "rationale": "theRationale",
        "onsetDate": "2025-02-03",
        "assessment": "theAssessment",
    }
    result = tested.command_from_json(parameters)
    expected = DiagnoseCommand(
        icd10_code="CODE12.3",
        background="theRationale",
        approximate_date_of_onset=date(2025, 2, 3),
        today_assessment="theAssessment",
        note_uuid="noteUuid",
    )
    assert result == expected

    calls = [
        call(
            tested.settings,
            ["keyword1", "keyword2", "keyword3"],
            ["ICD01", "ICD02", "ICD03"],
            "theRationale\n\ntheAssessment",
        ),
    ]
    assert condition_from.mock_calls == calls
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the diagnosed condition",
        "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the diagnosed condition",
        "rationale": "rationale about the diagnosis, as free text",
        "onsetDate": "YYYY-MM-DD",
        "assessment": "today's assessment of the condition, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Medical condition identified by the provider, including reasoning, current assessment, and onset date. "
                "There is one instruction per condition, and no instruction in the lack of.")
    assert result == expected


@patch.object(Diagnose, "current_conditions")
def test_instruction_constraints(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (conditions, "'Diagnose' cannot include: display1a, display2a, display3a."),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
