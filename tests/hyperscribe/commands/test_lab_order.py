from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.lab_order import LabOrder
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> LabOrder:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
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
    return LabOrder(settings, cache, identification)


def test_class():
    tested = LabOrder
    assert issubclass(tested, Base)


def test_schema_key():
    tested = LabOrder
    result = tested.schema_key()
    expected = "labOrder"
    assert result == expected


def test_staged_command_extract():
    tested = LabOrder
    tests = [
        ({}, None),
        (
            {
                "tests": [{"text": "test1"}, {"text": "test2"}, {"text": "test3"}],
                "comment": "theComment",
                "diagnosis": [{"text": "diagnose1"}, {"text": "diagnose2"}],
                "fasting_status": True,
            },
            CodedItem(
                label="test1/test2/test3: theComment (fasting: yes, diagnosis: diagnose1/diagnose2)",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "tests": [],
                "comment": "theComment",
                "diagnosis": [{"text": "diagnose1"}, {"text": "diagnose2"}],
                "fasting_status": True,
            },
            None,
        ),
        (
            {
                "tests": [{"text": "test1"}],
                "comment": "",
                "diagnosis": [{"text": "diagnose1"}],
                "fasting_status": False,
            },
            CodedItem(label="test1: n/a (fasting: no, diagnosis: diagnose1)", code="", uuid=""),
        ),
        (
            {"tests": [{"text": "test1"}], "comment": "", "diagnosis": [], "fasting_status": False},
            CodedItem(label="test1: n/a (fasting: no, diagnosis: n/a)", code="", uuid=""),
        ),
        (
            {"tests": [{"text": "test1"}], "comment": "", "diagnosis": [{"text": "diagnose1"}]},
            CodedItem(label="test1: n/a (fasting: n/a, diagnosis: diagnose1)", code="", uuid=""),
        ),
        (
            {"tests": [{"text": "test1"}], "comment": "", "diagnosis": "[]"},
            CodedItem(label="test1: n/a (fasting: n/a, diagnosis: n/a)", code="", uuid=""),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "preferred_lab_partner")
@patch.object(SelectorChat, "lab_test_from")
@patch.object(SelectorChat, "condition_from")
def test_command_from_json(condition_from, lab_test_from, preferred_lab_partner):
    chatter = MagicMock()

    def reset_mocks():
        condition_from.reset_mock()
        lab_test_from.reset_mock()
        preferred_lab_partner.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()

    comment = (
        "A very long comment to see that it is truncated after 127 characters. "
        "That is to go over the 127 characters, just in the middle of the sentence."
    )
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "labOrders": [
                {"labOrderKeywords": "lab1,lab2"},
                {"labOrderKeywords": "lab3"},
                {"labOrderKeywords": "lab4"},
            ],
            "conditions": [
                {"conditionKeywords": "condition1,condition2", "ICD10": "icd1,icd2"},
                {"conditionKeywords": "condition3", "ICD10": "icd3"},
                {"conditionKeywords": "condition4", "ICD10": "icd4"},
            ],
            "fastingRequired": True,
            "comment": comment,
        },
    }

    tests = [
        (
            CodedItem(uuid="", label="theLabPartner", code=""),
            LabOrderCommand(
                ordering_provider_key="providerUuid",
                fasting_required=True,
                comment="A very long comment to see that it is truncated after 127 characters. "
                "That is to go over the 127 characters, just in the middle",
                note_uuid="noteUuid",
                tests_order_codes=[],
                diagnosis_codes=["icd1", "icd3"],
            ),
        ),
        (
            CodedItem(uuid="uuidLab", label="theLabPartner", code=""),
            LabOrderCommand(
                lab_partner="uuidLab",
                ordering_provider_key="providerUuid",
                fasting_required=True,
                comment="A very long comment to see that it is truncated after 127 characters. "
                "That is to go over the 127 characters, just in the middle",
                note_uuid="noteUuid",
                tests_order_codes=["code2", "code4"],
                diagnosis_codes=["icd1", "icd3"],
            ),
        ),
    ]
    for lab_partner, expected in tests:
        condition_from.side_effect = [
            CodedItem(uuid="uuid1", label="condition1", code="icd1"),
            CodedItem(uuid="uuid3", label="condition3", code=""),
            CodedItem(uuid="uuid4", label="condition4", code="icd3"),
        ]
        lab_test_from.side_effect = [
            CodedItem(uuid="uuid2", label="lab2", code="code2"),
            CodedItem(uuid="uuid3", label="lab3", code=""),
            CodedItem(uuid="uuid4", label="lab4", code="code4"),
        ]
        preferred_lab_partner.side_effect = [lab_partner]
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        # ATTENTION the LabOrderCommand._get_error_details method checks the codes directly in the DB
        assert result.command.lab_partner == expected.lab_partner
        assert result.command.ordering_provider_key == expected.ordering_provider_key
        assert result.command.fasting_required == expected.fasting_required
        assert result.command.comment == expected.comment
        assert result.command.note_uuid == expected.note_uuid
        assert result.command.tests_order_codes == expected.tests_order_codes
        assert result.command.diagnosis_codes == expected.diagnosis_codes

        calls = [
            call(instruction, chatter, tested.settings, ["condition1", "condition2"], ["icd1", "icd2"], comment),
            call(instruction, chatter, tested.settings, ["condition3"], ["icd3"], comment),
            call(instruction, chatter, tested.settings, ["condition4"], ["icd4"], comment),
        ]
        assert condition_from.mock_calls == calls
        calls = []
        if lab_partner.uuid:
            calls = [
                call(
                    instruction,
                    chatter,
                    tested.cache,
                    "theLabPartner",
                    ["lab1", "lab2"],
                    comment,
                    ["condition1", "condition4"],
                ),
                call(
                    instruction,
                    chatter,
                    tested.cache,
                    "theLabPartner",
                    ["lab3"],
                    comment,
                    ["condition1", "condition4"],
                ),
                call(
                    instruction,
                    chatter,
                    tested.cache,
                    "theLabPartner",
                    ["lab4"],
                    comment,
                    ["condition1", "condition4"],
                ),
            ]
        assert lab_test_from.mock_calls == calls
        calls = [call()]
        assert preferred_lab_partner.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "labOrders": [{"labOrderKeywords": "comma separated keywords of up to 5 synonyms of each lab test to order"}],
        "conditions": [
            {
                "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition "
                "targeted by the lab tests",
                "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition targeted by the lab test",
            },
        ],
        "fastingRequired": "mandatory, True or False, as boolean",
        "comment": "rationale of the prescription, as free text limited to 128 characters",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Lab tests ordered, including the directions and the targeted conditions. "
        "There can be several lab orders in an instruction with the fasting requirement for the whole instruction "
        "and all necessary information for each lab order, "
        "and no instruction in the lack of."
    )
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
