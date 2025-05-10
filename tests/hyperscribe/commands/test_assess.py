from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.assess import AssessCommand

from hyperscribe.commands.assess import Assess
from hyperscribe.commands.base import Base
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Assess:
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
    return Assess(settings, cache, identification)


def test_class():
    tested = Assess
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Assess
    result = tested.schema_key()
    expected = "assess"
    assert result == expected


def test_staged_command_extract():
    tested = Assess
    tests = [
        ({}, None),
        ({
             "condition": {},
             "narrative": "better",
             "background": "theBackground",
         }, None),
        ({
             "condition": {
                 "text": "theCondition",
                 "annotations": ["theCode"],
             },
             "narrative": "theNarrative",
             "background": "theBackground",
         }, CodedItem(label="theCondition: theNarrative", code="", uuid="")),
        ({
             "condition": {
                 "text": "theCondition",
                 "annotations": ["theCode"],
             },
             "narrative": "",
             "background": "theBackground",
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(current_conditions):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (1, "theUuid2"),
        (2, "theUuid3"),
        (4, ""),
    ]
    for idx, exp_uuid in tests:
        current_conditions.side_effect = [conditions, conditions]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                'assessment': "theAssessment",
                'condition': 'display2a',
                'conditionIndex': idx,
                'rationale': 'theRationale',
                'status': 'stable',
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = AssessCommand(
            condition_id=exp_uuid,
            background="theRationale",
            status=AssessCommand.Status.STABLE,
            narrative="theAssessment",
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_command_parameters(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.command_parameters()
    expected = {
        'assessment': "today's assessment of the condition, as free text",
        'condition': 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        'conditionIndex': 'index of the Condition to assess, or -1, as integer',
        'rationale': 'rationale about the current assessment, as free text',
        'status': 'one of: improved/stable/deteriorated',
    }
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_description(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_description()
    expected = ("Today's assessment of a diagnosed condition (display1a, display2a, display3a). "
                "There can be only one assessment per condition per instruction, "
                "and no instruction in the lack of.")
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


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
    current_conditions.side_effect = [conditions]
    result = tested.instruction_constraints()
    expected = ("'Assess' has to be related to one of the following conditions: "
                "display1a (ICD-10: CODE12.3), "
                "display2a (ICD-10: CODE45), "
                "display3a (ICD-10: CODE98.76)")
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_is_available(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (conditions, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()
