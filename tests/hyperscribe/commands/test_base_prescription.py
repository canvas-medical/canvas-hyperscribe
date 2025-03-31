from decimal import Decimal
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.commands.base import Base
from hyperscribe.commands.base_prescription import BasePrescription
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> BasePrescription:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return BasePrescription(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = BasePrescription
    assert issubclass(tested, Base)


@patch.object(CanvasScience, "medication_details")
@patch.object(LimitedCache, "staged_commands_of")
@patch.object(LimitedCache, "current_allergies")
@patch.object(LimitedCache, "demographic__str__")
def test_medications_from(demographic, current_allergies, staged_commands_of, medication_details):
    chatter = MagicMock()

    def reset_mocks():
        demographic.reset_mock()
        current_allergies.reset_mock()
        staged_commands_of.reset_mock()
        medication_details.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
        "",
    ]
    user_prompts = {
        "with_conditions": [
            'Here is the comment provided by the healthcare provider in regards to the prescription:',
            '```text',
            'keywords: keyword1, keyword2, keyword3',
            ' -- ',
            'theComment',
            '```',
            '',
            "The prescription is intended to the patient's condition: theCondition.",
            '',
            'The choice of the medication has to also take into account that:',
            ' - the patient has this demographic,',
            " - the patient's medical record contains no information about allergies.",
            '',
            'Among the following medications, identify the most appropriate option:',
            '',
            ' * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)',
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
            '```',
            '',
        ],
        "no_condition": [
            'Here is the comment provided by the healthcare provider in regards to the prescription:',
            '```text',
            'keywords: keyword1, keyword2, keyword3',
            ' -- ',
            'theComment',
            '```',
            '',
            '',
            '',
            'The choice of the medication has to also take into account that:',
            ' - the patient has this demographic,',
            " - the patient's medical record contains no information about allergies.",
            '',
            'Among the following medications, identify the most appropriate option:',
            '',
            ' * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)',
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
            '```',
            '',
        ],
        "with_allergies": [
            'Here is the comment provided by the healthcare provider in regards to the prescription:',
            '```text',
            'keywords: keyword1, keyword2, keyword3',
            ' -- ',
            'theComment',
            '```',
            '',
            '',
            '',
            'The choice of the medication has to also take into account that:',
            ' - the patient has this demographic,',
            ' - the patient is allergic to:\n * allergy1\n * allergy2\n * allergy3.',
            '',
            'Among the following medications, identify the most appropriate option:',
            '',
            ' * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)',
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
            '```',
            '',
        ],
    }
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'fdbCode': {'type': 'integer', 'minimum': 1},
                'description': {'type': 'string', 'minLength': 1},
            },
            'required': ['fdbCode', 'description'],
            'additionalProperties': False,
        },
        'minItems': 1,
        'maxItems': 1,
    }]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    medications = [
        MedicationDetail(fdb_code="code123", description="labelA", quantities=[]),
        MedicationDetail(fdb_code="code369", description="labelB", quantities=[]),
        MedicationDetail(fdb_code="code752", description="labelC", quantities=[]),
    ]
    allergies = [
        CodedItem(label="allergy1", uuid="uuid1", code="code1"),
        CodedItem(label="allergy2", uuid="uuid2", code="code2"),
        CodedItem(label="allergy3", uuid="uuid3", code="code3"),
    ]

    tested = helper_instance()

    # with condition
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    result = tested.medications_from(chatter, "theComment", keywords, "theCondition")
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["with_conditions"], schemas)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without condition
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    result = tested.medications_from(chatter, "theComment", keywords, "")
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["no_condition"], schemas)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without allergies
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [allergies[:2]]
    staged_commands_of.side_effect = [allergies[2:]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    result = tested.medications_from(chatter, "theComment", keywords, "")
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["with_allergies"], schemas)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without response
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[]]
    result = tested.medications_from(chatter, "theComment", keywords, "")
    assert result == []

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts["no_condition"], schemas)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medication
    demographic.side_effect = []
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [[]]
    chatter.single_conversation.side_effect = []
    result = tested.medications_from(chatter, "theComment", keywords, "theCondition")
    assert result == []

    assert demographic.mock_calls == []
    assert current_allergies.mock_calls == []
    assert staged_commands_of.mock_calls == []
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(LimitedCache, "demographic__str__")
def test_set_medication_dosage(demographic):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        demographic.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to compute the quantity to dispense and the number of refills for a prescription.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the prescription of the medication labelB:',
        '```text',
        'theComment',
        '```',
        '',
        'The medication is provided as 7, description1.',
        '',
        'Based on this information, what are the quantity to dispense and the number of refills in order to fulfill the 11 supply days?',
        '',
        'The exact quantities and refill have to also take into account that the patient has this demographic.',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"quantityToDispense": "mandatory, quantity to dispense, as decimal", '
        '"refills": "mandatory, refills allowed, as integer", '
        '"noteToPharmacist": "note to the pharmacist, as free text", '
        '"informationToPatient": "directions to the patient on how to use the medication, specifying the quantity, '
        'the form (e.g. tablets, drops, puffs, etc), '
        'the frequency and/or max daily frequency, and '
        'the route of use (e.g. by mouth, applied to skin, dropped in eye, etc), as free text"}]',
        '```',
        '',
    ]
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'quantityToDispense': {'type': 'number', 'exclusiveMinimum': 0},
                'refills': {'type': 'integer', 'minimum': 0},
                'noteToPharmacist': {'type': 'string'},
                'informationToPatient': {'type': 'string', 'minLength': 1},
            },
            'required': ['quantityToDispense', 'refills', 'informationToPatient'],
            'additionalProperties': False,
        },
        'minItems': 1,
        'maxItems': 1,
    }]
    medication = MedicationDetail(
        fdb_code="code369",
        description="labelB",
        quantities=[
            MedicationDetailQuantity(
                quantity="7",
                representative_ndc="ndc1",
                ncpdp_quantity_qualifier_code="qualifier1",
                ncpdp_quantity_qualifier_description="description1",
            ),
            MedicationDetailQuantity(
                quantity="3",
                representative_ndc="ndc2",
                ncpdp_quantity_qualifier_code="qualifier2",
                ncpdp_quantity_qualifier_description="description2",
            ),
        ],
    )

    tested = helper_instance()

    # with response
    tests = [
        (
            PrescribeCommand(days_supply=11),
            PrescribeCommand(
                days_supply=11,
                fdb_code="code369",
                type_to_dispense={
                    'representative_ndc': 'ndc1',
                    'ncpdp_quantity_qualifier_code': 'qualifier1',
                },
                quantity_to_dispense=Decimal("8.3"),
                refills=3,
                note_to_pharmacist="theNoteToPharmacist",
                sig="theInformationToPatient",
            )
        ),
        (
            AdjustPrescriptionCommand(days_supply=11, fdb_code="code985"),
            AdjustPrescriptionCommand(
                days_supply=11,
                fdb_code="code985",
                new_fdb_code="code369",
                type_to_dispense={
                    'representative_ndc': 'ndc1',
                    'ncpdp_quantity_qualifier_code': 'qualifier1',
                },
                quantity_to_dispense=Decimal("8.3"),
                refills=3,
                note_to_pharmacist="theNoteToPharmacist",
                sig="theInformationToPatient",
            )
        ),
    ]
    for command, expected in tests:
        demographic.side_effect = ["the patient has this demographic"]
        chatter.single_conversation.side_effect = [[{
            "quantityToDispense": "8.3",
            "refills": 3,
            "noteToPharmacist": "theNoteToPharmacist",
            "informationToPatient": "theInformationToPatient",
        }]]
        tested.set_medication_dosage(chatter, "theComment", command, medication)
        assert command == expected

        calls = [call()]
        assert demographic.mock_calls == calls
        calls = [call.single_conversation(system_prompt, user_prompt, schemas)]
        assert chatter.mock_calls == calls
        reset_mocks()

    # no response
    command = PrescribeCommand(days_supply=11)
    demographic.side_effect = ["the patient has this demographic"]
    chatter.single_conversation.side_effect = [[]]
    tested.set_medication_dosage(chatter, "theComment", command, medication)
    expected = PrescribeCommand(
        days_supply=11,
        fdb_code="code369",
        type_to_dispense={
            'representative_ndc': 'ndc1',
            'ncpdp_quantity_qualifier_code': 'qualifier1',
        },
    )
    assert command == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas)]
    assert chatter.mock_calls == calls
    reset_mocks()
