from unittest.mock import patch, call

from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.lab_order import LabOrder
from commander.protocols.selector_chat import SelectorChat
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings
from commander.protocols.temporary_data import TemporaryData


def helper_instance() -> LabOrder:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return LabOrder(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = LabOrder
    assert issubclass(tested, Base)


def test_schema_key():
    tested = LabOrder
    result = tested.schema_key()
    expected = "labOrder"
    assert result == expected


@patch.object(SelectorChat, "lab_test_from")
@patch.object(SelectorChat, "condition_from")
def test_command_from_json(condition_from, lab_test_from):
    def reset_mocks():
        condition_from.reset_mock()
        lab_test_from.reset_mock()

    tested = helper_instance()

    comment = ("A very long comment to see that it is truncated after 127 characters. "
               "That is to go over the 127 characters, just in the middle of the sentence.")
    parameters = {
        "labOrders": [
            {"labOrderKeyword": "lab1,lab2"},
            {"labOrderKeyword": "lab3"},
            {"labOrderKeyword": "lab4"},
        ],
        "conditions": [
            {"conditionKeywords": "condition1,condition2", "ICD10": "icd1,icd2"},
            {"conditionKeywords": "condition3", "ICD10": "icd3"},
            {"conditionKeywords": "condition4", "ICD10": "icd4"},
        ],
        "fastingRequired": True,
        "comment": comment,
    }
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

    result = tested.command_from_json(parameters)
    expected = LabOrderCommand(
        lab_partner="Generic Lab",
        ordering_provider_key="providerUuid",
        fasting_required=True,
        comment="A very long comment to see that it is truncated after 127 characters. "
                "That is to go over the 127 characters, just in the middle",
        note_uuid="noteUuid",
        tests_order_codes=['code2', 'code4'],
        diagnosis_codes=['icd1', 'icd3'],
    )
    assert result == expected

    calls = [
        call(tested.settings, ['condition1', 'condition2'], ['icd1', 'icd2'], comment),
        call(tested.settings, ['condition3'], ['icd3'], comment),
        call(tested.settings, ['condition4'], ['icd4'], comment),
    ]
    assert condition_from.mock_calls == calls
    calls = [
        call(tested.settings, 'Generic Lab', ['lab1', 'lab2'], comment, ['condition1', 'condition4']),
        call(tested.settings, 'Generic Lab', ['lab3'], comment, ['condition1', 'condition4']),
        call(tested.settings, 'Generic Lab', ['lab4'], comment, ['condition1', 'condition4']),

    ]
    assert lab_test_from.mock_calls == calls
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "labOrders": [
            {
                "labOrderKeyword": "comma separated keywords of up to 5 synonyms of each lab test to order",
            },
        ],
        "conditions": [
            {
                "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition targeted by the lab tests",
                "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition targeted by the lab test",
            },
        ],
        "fastingRequired": "mandatory, True or False, as boolean",
        "comment": "rational of the prescription, as free text limited to 128 characters",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Lab tests ordered, including the directions and the targeted condition. "
                "There can be several lab orders in an instruction with the fasting requirement for the whole instruction "
                "and all necessary information for each lab order, "
                "and no instruction in the lack of.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


@patch.object(TemporaryData, "access_to_lab_data")
def test_is_available(access_to_lab_data):
    def reset_mocks():
        access_to_lab_data.reset_mock()

    tested = helper_instance()

    tests = [
        (True, True),
        (False, False),
    ]
    for side_effect, expected in tests:
        access_to_lab_data.side_effect = [side_effect]

        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert access_to_lab_data.mock_calls == calls
        reset_mocks()
