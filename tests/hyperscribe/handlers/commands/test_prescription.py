from decimal import Decimal
from unittest.mock import patch, call

from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.commands.prescription import Prescription
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.medication_detail import MedicationDetail
from hyperscribe.handlers.structures.medication_detail_quantity import MedicationDetailQuantity
from hyperscribe.handlers.structures.settings import Settings
from hyperscribe.handlers.structures.vendor_key import VendorKey


def helper_instance() -> Prescription:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return Prescription(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Prescription
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Prescription
    result = tested.schema_key()
    expected = "prescribe"
    assert result == expected


def test_staged_command_extract():
    tested = Prescription
    tests = [
        ({}, None),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "theMedication",
                 "value": 292907,
             },
             "days_supply": 7,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": "3"
         }, CodedItem(
            label="theMedication: theSig (dispense: 3, supply days: 7, refills: 2, substitution: allowed, indications: theIndication1/theIndication2/theIndication3)",
            code="292907", uuid="")),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "",
                 "value": 292907,
             },
             "days_supply": 7,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": "3"
         }, None),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": None,
             },
             "days_supply": None,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": None,
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": None
         }, CodedItem(
            label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, indications: theIndication1/theIndication2/theIndication3)",
            code="", uuid="")),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": None,
             },
             "days_supply": None,
             "indications": [],
             "substitutions": None,
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": None
         }, CodedItem(label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, indications: n/a)", code="",
                      uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(Helper, "chatter")
@patch.object(CanvasScience, "medication_details")
@patch.object(LimitedCache, "staged_commands_of")
@patch.object(LimitedCache, "current_allergies")
@patch.object(LimitedCache, "demographic__str__")
def test_medications_from(demographic, current_allergies, staged_commands_of, medication_details, chatter):
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
    chatter.return_value.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    result = tested.medications_from("theComment", keywords, "theCondition")
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompts["with_conditions"], schemas),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without condition
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.return_value.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    result = tested.medications_from("theComment", keywords, "")
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompts["no_condition"], schemas),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without allergies
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [allergies[:2]]
    staged_commands_of.side_effect = [allergies[2:]]
    medication_details.side_effect = [medications]
    chatter.return_value.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]
    result = tested.medications_from("theComment", keywords, "")
    expected = [MedicationDetail(fdb_code="code369", description="labelB", quantities=[])]
    assert result == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompts["with_allergies"],schemas),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # without response
    demographic.side_effect = ["the patient has this demographic"]
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [medications]
    chatter.return_value.single_conversation.side_effect = [[]]
    result = tested.medications_from("theComment", keywords, "")
    assert result == []

    calls = [call()]
    assert demographic.mock_calls == calls
    assert current_allergies.mock_calls == calls
    calls = [call(["allergy"])]
    assert staged_commands_of.mock_calls == calls
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompts["no_condition"], schemas),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medication
    demographic.side_effect = []
    current_allergies.side_effect = [[]]
    staged_commands_of.side_effect = [[]]
    medication_details.side_effect = [[]]
    chatter.return_value.single_conversation.side_effect = []
    result = tested.medications_from("theComment", keywords, "theCondition")
    assert result == []

    assert demographic.mock_calls == []
    assert current_allergies.mock_calls == []
    assert staged_commands_of.mock_calls == []
    calls = [call('scienceHost', keywords)]
    assert medication_details.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(Helper, "chatter")
@patch.object(LimitedCache, "demographic__str__")
def test_set_medication_dosage(demographic, chatter):
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
    command = PrescribeCommand(days_supply=11)
    demographic.side_effect = ["the patient has this demographic"]
    chatter.return_value.single_conversation.side_effect = [[{
        "quantityToDispense": "8.3",
        "refills": 3,
        "noteToPharmacist": "theNoteToPharmacist",
        "informationToPatient": "theInformationToPatient",
    }]]
    tested.set_medication_dosage("theComment", command, medication)
    expected = PrescribeCommand(
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
    assert command == expected

    calls = [call()]
    assert demographic.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt, schemas),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no response
    command = PrescribeCommand(days_supply=11)
    demographic.side_effect = ["the patient has this demographic"]
    chatter.return_value.single_conversation.side_effect = [[]]
    tested.set_medication_dosage("theComment", command, medication)
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
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt, schemas),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()


@patch.object(Prescription, "set_medication_dosage")
@patch.object(Prescription, "medications_from")
@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(current_conditions, medications_from, set_medication_dosage):
    def reset_mocks():
        current_conditions.reset_mock()
        medications_from.reset_mock()
        set_medication_dosage.reset_mock()

    tested = helper_instance()

    medication = MedicationDetail(fdb_code="code369", description="labelB", quantities=[
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
    ])
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    keywords = ["keyword1", "keyword2", "keyword3"]

    # with condition
    tests = [
        (1, "display2a", ["CODE45"], [call(), call()]),
        (2, "display3a", ["CODE9876"], [call(), call()]),
        (4, "", [], [call()]),
    ]
    for idx, condition_label, condition_icd10, condition_calls in tests:
        current_conditions.side_effect = [conditions, conditions]
        medications_from.side_effect = [[medication]]

        parameters = {
            'keywords': 'keyword1,keyword2,keyword3',
            'sig': 'theSig',
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
            "condition": "theCondition",
            "conditionIndex": idx,
        }
        result = tested.command_from_json(parameters)
        expected = PrescribeCommand(
            sig="theSig",
            days_supply=11,
            substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
            prescriber_id="providerUuid",
            note_uuid="noteUuid",
        )
        if condition_icd10:
            expected.icd10_codes = condition_icd10
        assert result == expected, f"----> {idx}"
        assert current_conditions.mock_calls == condition_calls
        calls = [call("theComment", keywords, condition_label)]
        assert medications_from.mock_calls == calls
        calls = [call("theComment", expected, medication)]
        assert set_medication_dosage.mock_calls == calls
        reset_mocks()

    # no condition
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication]]

    parameters = {
        'keywords': 'keyword1,keyword2,keyword3',
        'sig': 'theSig',
        "suppliedDays": 11,
        "substitution": "not_allowed",
        "comment": "theComment",
    }
    result = tested.command_from_json(parameters)
    expected = PrescribeCommand(
        sig="theSig",
        days_supply=11,
        substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [call("theComment", keywords, "")]
    assert medications_from.mock_calls == calls
    calls = [call("theComment", expected, medication)]
    assert set_medication_dosage.mock_calls == calls
    reset_mocks()

    # no medication
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[]]

    parameters = {
        'keywords': 'keyword1,keyword2,keyword3',
        'sig': 'theSig',
        "suppliedDays": 11,
        "substitution": "not_allowed",
        "comment": "theComment",
    }
    result = tested.command_from_json(parameters)
    expected = PrescribeCommand(
        sig="theSig",
        days_supply=11,
        substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [call("theComment", keywords, "")]
    assert medications_from.mock_calls == calls
    assert set_medication_dosage.mock_calls == []
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
    tests = [
        (conditions, {
            "keywords": "comma separated keywords of up to 5 synonyms of the medication to prescribe",
            "sig": "directions, as free text",
            "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following the standard practices, as integer",
            "substitution": "one of: allowed/not_allowed",
            "comment": "rational of the prescription, as free text",
            "condition": "None or, one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)",
            "conditionIndex": "index of the condition for which the medication is prescribed, as integer or -1 if the prescription is not related to any listed condition",
        }),
        ([], {
            "keywords": "comma separated keywords of up to 5 synonyms of the medication to prescribe",
            "sig": "directions, as free text",
            "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following the standard practices, as integer",
            "substitution": "one of: allowed/not_allowed",
            "comment": "rational of the prescription, as free text",
        }),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.command_parameters()
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Medication prescription, including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one prescription per instruction, and no instruction in the lack of.")
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
