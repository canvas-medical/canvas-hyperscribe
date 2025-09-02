import json
from datetime import date
from hashlib import md5
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.diagnose import Diagnose
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Diagnose:
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
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return Diagnose(settings, cache, identification)


def test_class():
    tested = Diagnose
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Diagnose
    result = tested.schema_key()
    expected = "diagnose"
    assert result == expected


def test_staged_command_extract():
    tested = Diagnose
    tests = [
        ({}, None),
        (
            {
                "diagnose": {"text": "theDiagnosis", "value": "theCode"},
                "background": "theBackground",
                "today_assessment": "theAssessment",
            },
            CodedItem(label="theDiagnosis (theAssessment)", code="theCode", uuid=""),
        ),
        (
            {
                "diagnose": {"text": "theDiagnosis", "value": "theCode"},
                "background": "theBackground",
                "today_assessment": "",
            },
            CodedItem(label="theDiagnosis (n/a)", code="theCode", uuid=""),
        ),
        (
            {
                "diagnose": {"text": "", "value": "theCode"},
                "background": "theBackground",
                "today_assessment": "theAssessment",
            },
            None,
        ),
        (
            {
                "diagnose": {"text": "theDiagnosis", "value": ""},
                "background": "theBackground",
                "today_assessment": "theAssessment",
            },
            None,
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(SelectorChat, "condition_from")
@patch.object(Diagnose, "add_code2description")
def test_command_from_json(add_code2description, condition_from):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        condition_from.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()
    condition_from.side_effect = [CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3")]
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "keywords": "keyword1,keyword2,keyword3",
            "ICD10": "ICD01,ICD02,ICD03",
            "rationale": "theRationale",
            "onsetDate": "2025-02-03",
            "assessment": "theAssessment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = DiagnoseCommand(
        icd10_code="CODE12.3",
        background="theRationale",
        approximate_date_of_onset=date(2025, 2, 3),
        today_assessment="theAssessment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected

    calls = [call("theUuid1", "display1a")]
    assert add_code2description.mock_calls == calls
    calls = [
        call(
            instruction,
            chatter,
            ["keyword1", "keyword2", "keyword3"],
            ["ICD01", "ICD02", "ICD03"],
            "theRationale\n\ntheAssessment",
        ),
    ]
    assert condition_from.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "",
        "ICD10": "",
        "rationale": "",
        "onsetDate": "",
        "assessment": "",
    }
    assert result == expected


def test_command_parameters_schema():
    tested = helper_instance()
    result = tested.command_parameters_schemas()
    expected = "de777483065675d98757de2eb0ea79c2"
    assert md5(json.dumps(result).encode()).hexdigest() == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Medical condition identified by the provider; the necessary information to report includes: "
        "- the medical condition itself, "
        "- all reasoning explicitly mentioned in the transcript, "
        "- current detailed assessment as mentioned in the transcript, and "
        "- onset date, even for today. "
        "There is one and only one condition per instruction with all necessary information, "
        "and no instruction in the lack of."
    )
    assert result == expected


@patch.object(LimitedCache, "current_conditions")
def test_instruction_constraints(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [(conditions, "'Diagnose' cannot include: display1a, display2a, display3a."), ([], "")]
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
