from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.reason_for_visit import ReasonForVisit
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(structured_rfv: bool = False) -> ReasonForVisit:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=structured_rfv,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return ReasonForVisit(settings, cache, identification)


def test_class():
    tested = ReasonForVisit
    assert issubclass(tested, Base)


def test_schema_key():
    tested = ReasonForVisit
    result = tested.schema_key()
    expected = "reasonForVisit"
    assert result == expected


def test_staged_command_extract():
    tested = ReasonForVisit
    tests = [
        ({}, None),
        ({
             "coding": {"text": "theStructuredRfV"},
             "comment": "theComment"
         }, CodedItem(label="theStructuredRfV", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "comment": "theComment"
         }, CodedItem(label="theComment", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "comment": ""
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_command_from_json(existing_reason_for_visits):
    chatter = MagicMock()

    def reset_mocks():
        existing_reason_for_visits.reset_mock()
        chatter.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "reasonForVisit": "theReasonForVisit",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = ReasonForVisitCommand(
        comment="theReasonForVisit",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert existing_reason_for_visits.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    tests = [
        (1, "theUuid2", True),
        (2, "theUuid3", True),
        (4, None, False),
    ]
    for idx, exp_uuid, exp_structured in tests:
        existing_reason_for_visits.side_effect = [reason_for_visits]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "reasonForVisit": "theReasonForVisit",
                "reasonForVisitIndex": idx,
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = ReasonForVisitCommand(
            comment="theReasonForVisit",
            note_uuid="noteUuid",
        )
        if exp_structured:
            command.structured = exp_structured
        if exp_uuid:
            command.coding = exp_uuid
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call()]
        assert existing_reason_for_visits.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_command_parameters(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    result = tested.command_parameters()
    expected = {
        "reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text",
    }
    assert result == expected
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.command_parameters()
    expected = {
        "reasonForVisit": "one of: display1/display2/display3",
        "reasonForVisitIndex": "the index of the reason for visit, as integer",
    }
    assert result == expected
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_instruction_description(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    result = tested.instruction_description()
    expected = ("Patient's reported reason or impetus for the visit, extremely concise. "
                "There can be multiple reasons within an instruction, "
                "but only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently merging all reasons.")
    assert result == expected
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.instruction_description()
    expected = ("Patient's reported reason or impetus for the visit within: display1, display2, display3. "
                "There can be only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently.")
    assert result == expected
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_instruction_constraints(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.instruction_constraints()
    expected = "'ReasonForVisit' has to be one of the following: display1, display2, display3"
    assert result == expected
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_is_available(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    result = tested.is_available()
    assert result is True
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    # -- no reason for visit defined
    existing_reason_for_visits.side_effect = [[]]
    result = tested.is_available()
    assert result is False
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()
    # -- some reasons for visit defined
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.is_available()
    assert result is True
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()
