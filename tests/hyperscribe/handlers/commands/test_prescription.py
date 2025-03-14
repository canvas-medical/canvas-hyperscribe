from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.handlers.commands.base_prescription import BasePrescription
from hyperscribe.handlers.commands.prescription import Prescription
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
    assert issubclass(tested, BasePrescription)


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
            label="theMedication: theSig (dispense: 3, supply days: 7, refills: 2, substitution: allowed, related conditions: theIndication1/theIndication2/theIndication3)",
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
            label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, related conditions: theIndication1/theIndication2/theIndication3)",
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
         }, CodedItem(label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, related conditions: n/a)", code="",
                      uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(Prescription, "set_medication_dosage")
@patch.object(Prescription, "medications_from")
@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(current_conditions, medications_from, set_medication_dosage):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
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
        result = tested.command_from_json(chatter, parameters)
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
        calls = [call(chatter, "theComment", keywords, condition_label)]
        assert medications_from.mock_calls == calls
        calls = [call(chatter, "theComment", expected, medication)]
        assert set_medication_dosage.mock_calls == calls
        assert chatter.mock_calls == []
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
    result = tested.command_from_json(chatter, parameters)
    expected = PrescribeCommand(
        sig="theSig",
        days_supply=11,
        substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [call(chatter, "theComment", keywords, "")]
    assert medications_from.mock_calls == calls
    calls = [call(chatter, "theComment", expected, medication)]
    assert set_medication_dosage.mock_calls == calls
    assert chatter.mock_calls == []
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
    result = tested.command_from_json(chatter, parameters)
    expected = PrescribeCommand(
        sig="theSig",
        days_supply=11,
        substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [call(chatter, "theComment", keywords, "")]
    assert medications_from.mock_calls == calls
    assert set_medication_dosage.mock_calls == []
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
