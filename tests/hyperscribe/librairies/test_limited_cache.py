from datetime import date
from unittest.mock import patch, call
from uuid import uuid5, NAMESPACE_DNS

from canvas_sdk.commands.constants import CodeSystems
from canvas_sdk.v1.data import (
    Command, Condition, ConditionCoding, MedicationCoding,
    Medication, AllergyIntolerance, AllergyIntoleranceCoding,
    Patient, Observation, NoteType, ReasonForVisitSettingCoding,
    Staff, PracticeLocation, PracticeLocationSetting, TaskLabel)
from canvas_sdk.v1.data.lab import LabPartner
from django.db.models.expressions import When, Value, Case

from hyperscribe.handlers.temporary_data import ChargeDescriptionMaster
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.charge_description import ChargeDescription
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.medication_cached import MedicationCached


def test___init__():
    staged_commands_to_coded_items = {
        "keyX": [CodedItem(code="code1", label="label1", uuid="uuid1")],
        "keyY": [],
        "keyZ": [
            CodedItem(code="code3", label="label3", uuid="uuid3"),
            CodedItem(code="code2", label="label2", uuid="uuid2"),
        ],
    }
    tested = LimitedCache("patientUuid", "providerUuid", staged_commands_to_coded_items)
    assert tested.patient_uuid == "patientUuid"
    assert tested.provider_uuid == "providerUuid"
    assert tested._settings == {}
    assert tested._allergies is None
    assert tested._condition_history is None
    assert tested._conditions is None
    assert tested._demographic is None
    assert tested._family_history is None
    assert tested._goals is None
    assert tested._medications is None
    assert tested._note_type is None
    assert tested._preferred_lab_partner is None
    assert tested._reason_for_visit is None
    assert tested._surgery_history is None
    assert tested._staged_commands == staged_commands_to_coded_items
    assert tested._charge_descriptions is None


@patch.object(ChargeDescriptionMaster, "objects")
def test_charge_descriptions(charge_description_db):
    def reset_mocks():
        charge_description_db.reset_mock()

    charge_descriptions = [
        ChargeDescriptionMaster(cpt_code="code123", name="theFullNameA", short_name="theShortNameA"),
        ChargeDescriptionMaster(cpt_code="code369", name="theFullNameB", short_name="theShortNameB"),
        ChargeDescriptionMaster(cpt_code="code486", name="theFullNameG", short_name="theShortNameD"),
        ChargeDescriptionMaster(cpt_code="code565", name="theFullNameF", short_name="theShortNameB"),
        ChargeDescriptionMaster(cpt_code="code752", name="theFullNameC", short_name="theShortNameC"),
        ChargeDescriptionMaster(cpt_code="code753", name="theFullNameE", short_name="theShortNameA"),
        ChargeDescriptionMaster(cpt_code="code754", name="theFullNameD", short_name="theShortNameA"),
    ]

    with patch.object(Constants, 'MAX_CHARGE_DESCRIPTIONS', 99):
        # too many records
        charge_description_db.count.side_effect = [100]
        charge_description_db.all.return_value.order_by.side_effect = []
        tested = LimitedCache("patientUuid", "providerUuid", {})
        result = tested.charge_descriptions()
        assert result == []
        calls = [
            call.count(),
        ]
        assert charge_description_db.mock_calls == calls
        reset_mocks()

        result = tested.charge_descriptions()
        assert result == []
        assert charge_description_db.mock_calls == []
        reset_mocks()

        # not too many records
        charge_description_db.count.side_effect = [99]
        charge_description_db.all.return_value.order_by.side_effect = [charge_descriptions]
        tested = LimitedCache("patientUuid", "providerUuid", {})
        result = tested.charge_descriptions()
        expected = [
            ChargeDescription(full_name='theFullNameD', short_name='theShortNameA', cpt_code='code754'),
            ChargeDescription(full_name='theFullNameF', short_name='theShortNameB', cpt_code='code565'),
            ChargeDescription(full_name='theFullNameG', short_name='theShortNameD', cpt_code='code486'),
            ChargeDescription(full_name='theFullNameC', short_name='theShortNameC', cpt_code='code752'),
        ]
        assert result == expected
        calls = [
            call.count(),
            call.all(),
            call.all().order_by('cpt_code'),
        ]
        assert charge_description_db.mock_calls == calls
        reset_mocks()

        result = tested.charge_descriptions()
        assert result == expected
        assert charge_description_db.mock_calls == []
        reset_mocks()


@patch.object(Condition, 'codings')
@patch.object(Condition, 'objects')
def test_retrieve_conditions(condition_db, codings_db):
    def reset_mocks():
        condition_db.reset_mock()
        codings_db.reset_mock()

    codings_db.filter.return_value.annotate.return_value.order_by.return_value.first.side_effect = [
        ConditionCoding(system="ICD-10", display="display1a", code="CODE123"),
        ConditionCoding(system="ICD-10", display="display4a", code="CODE45"),
        ConditionCoding(system="http://snomed.info/sct", display="display2c", code="44"),
        ConditionCoding(system="ICD-10", display="display3a", code="CODE9876"),
        ConditionCoding(system="ICD-10", display="display5a", code="CODE8888"),
        ConditionCoding(system="ImpossibleCase", display="ImpossibleCase", code="ImpossibleCase"),
        None,
    ]
    condition_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Condition(id=uuid5(NAMESPACE_DNS, "1"), clinical_status="active"),
            Condition(id=uuid5(NAMESPACE_DNS, "2"), clinical_status="resolved"),
            Condition(id=uuid5(NAMESPACE_DNS, "3"), clinical_status="resolved"),
            Condition(id=uuid5(NAMESPACE_DNS, "4"), clinical_status="resolved"),
            Condition(id=uuid5(NAMESPACE_DNS, "5"), clinical_status="active"),
            Condition(id=uuid5(NAMESPACE_DNS, "6"), clinical_status="resolved"),
            Condition(id=uuid5(NAMESPACE_DNS, "6"), clinical_status="active"),
        ],
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    tested.retrieve_conditions()

    result = tested._conditions
    expected = [
        CodedItem(uuid='b04965e6-a9bb-591f-8f8a-1adcb2c8dc39', label='display1a', code='CODE12.3'),
        CodedItem(uuid='c8691da2-158a-5ed6-8537-0e6f140801f2', label='display5a', code='CODE88.88'),
    ]
    assert result == expected
    result = tested._condition_history
    expected = [
        CodedItem(uuid='4b166dbe-d99d-5091-abdd-95b83330ed3a', label='display4a', code='CODE45'),
        CodedItem(uuid='6ed955c6-506a-5343-9be4-2c0afae02eef', label='display3a', code='CODE98.76'),
    ]
    assert result == expected
    result = tested._surgery_history
    expected = [
        CodedItem(uuid='98123fde-012f-5ff3-8b50-881449dac91a', label='display2c', code='44'),
    ]
    assert result == expected

    calls = [
        call.committed(),
        call.committed().for_patient('patientUuid'),
        call.committed().for_patient().filter(clinical_status__in=["active", "resolved"]),
        call.committed().for_patient().filter().order_by('-dbid'),
    ]
    assert condition_db.mock_calls == calls

    calls = [
        call.filter(system__in=[CodeSystems.ICD10, CodeSystems.SNOMED]),
        call.filter().annotate(system_order=Case(When(system=CodeSystems.ICD10, then=Value(1)), When(system=CodeSystems.SNOMED, then=Value(2)))),
        call.filter().annotate().order_by('system_order'),
        call.filter().annotate().order_by().first(),
    ]
    assert codings_db.mock_calls == calls * 7
    reset_mocks()


def test_staged_commands_of():
    coded_items = [
        CodedItem(code="code1", label="label1", uuid="uuid1"),
        CodedItem(code="code3", label="label3", uuid="uuid3"),
        CodedItem(code="code2", label="label2", uuid="uuid2"),
    ]

    staged_commands_to_coded_items = {
        "keyX": [coded_items[0]],
        "keyY": [],
        "keyZ": [coded_items[1], coded_items[2]],
    }
    tested = LimitedCache("patientUuid", "providerUuid", staged_commands_to_coded_items)

    tests = [
        (["keyX"], coded_items[:1]),
        (["keyY"], []),
        (["keyZ"], coded_items[1:]),
        (["keyX", "keyY"], coded_items[:1]),
        (["keyX", "keyZ"], coded_items),
    ]
    for keys, expected in tests:
        result = tested.staged_commands_of(keys)
        assert result == expected


def test_staged_commands_as_instructions():
    coded_items = [
        CodedItem(code="code1", label="label1", uuid="uuid1"),
        CodedItem(code="code3", label="label3", uuid="uuid3"),
        CodedItem(code="code2", label="label2", uuid="uuid2"),
    ]

    staged_commands_to_coded_items = {
        "keyX": [coded_items[0]],
        "keyY": [],
        "keyZ": [coded_items[1], coded_items[2]],
    }
    tested = LimitedCache("patientUuid", "providerUuid", staged_commands_to_coded_items)

    schema_key2instruction = {
        "keyX": "Instruction1",
        "keyY": "Instruction2",
        "keyZ": "Instruction3",
    }
    result = tested.staged_commands_as_instructions(schema_key2instruction)
    expected = Instruction.load_from_json([
        {'uuid': 'uuid1', 'instruction': 'Instruction1', 'information': 'label1', 'isNew': True, 'isUpdated': False},
        {'uuid': 'uuid3', 'instruction': 'Instruction3', 'information': 'label3', 'isNew': True, 'isUpdated': False},
        {'uuid': 'uuid2', 'instruction': 'Instruction3', 'information': 'label2', 'isNew': True, 'isUpdated': False},

    ])
    assert result == expected


@patch.object(Command, 'objects')
def test_current_goals(command_db):
    def reset_mocks():
        command_db.reset_mock()

    command_db.filter.return_value.order_by.side_effect = [[
        Command(id=uuid5(NAMESPACE_DNS, "1"), dbid=258, data={"goal_statement": "statement1"}),
        Command(id=uuid5(NAMESPACE_DNS, "2"), dbid=259, data={"goal_statement": "statement2"}),
        Command(id=uuid5(NAMESPACE_DNS, "3"), dbid=267, data={"goal_statement": "statement3"}),
    ]]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", code="258", label="statement1"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", code="259", label="statement2"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", code="267", label="statement3"),
    ]

    result = tested.current_goals()
    assert result == expected
    assert tested._goals == expected
    calls = [
        call.filter(patient__id="patientUuid", schema_key="goal"),
        call.filter().order_by('-dbid'),
    ]
    assert command_db.mock_calls == calls
    reset_mocks()

    result = tested.current_goals()
    assert result == expected
    assert tested._goals == expected
    assert command_db.mock_calls == []
    reset_mocks()


@patch.object(LimitedCache, 'retrieve_conditions')
def test_current_conditions(retrieve_conditions):
    def reset_mocks():
        retrieve_conditions.reset_mock()

    tested = LimitedCache("patientUuid", "providerUuid", {})
    assert tested._conditions is None
    result = tested.current_conditions()
    assert result == []
    calls = [call()]
    assert retrieve_conditions.mock_calls == calls
    reset_mocks()

    tested._conditions = []
    result = tested.current_conditions()
    assert result == []
    assert tested._conditions == []
    assert retrieve_conditions.mock_calls == []
    reset_mocks()


@patch.object(Medication, 'codings')
@patch.object(Medication, 'objects')
def test_current_medications(medication_db, codings_db):
    def reset_mocks():
        medication_db.reset_mock()
        codings_db.reset_mock()

    rx_norm = "http://www.nlm.nih.gov/research/umls/rxnorm"
    fdb = "http://www.fdbhealth.com/"

    codings_db.all.side_effect = [
        [
            MedicationCoding(system=rx_norm, display="display1a", code="CODE123"),
            MedicationCoding(system="OTHER", display="display1b", code="CODE321"),
            MedicationCoding(system=fdb, display="display1c", code="CODE231"),
        ],
        [
            MedicationCoding(system=rx_norm, display="display2a", code="CODE45"),
            MedicationCoding(system="OTHER", display="display2b", code="CODE54"),
        ],
        [
            MedicationCoding(system="OTHER", display="display3b", code="CODE6789"),
            MedicationCoding(system=rx_norm, display="display3a", code="CODE9876"),
            MedicationCoding(system=fdb, display="display3c", code="CODE8976"),
        ],
        [
            MedicationCoding(system=fdb, display="display4c", code="CODE5654"),
        ],
    ]
    medication_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Medication(id=uuid5(NAMESPACE_DNS, "1"), national_drug_code="ndc1", potency_unit_code="puc1"),
            Medication(id=uuid5(NAMESPACE_DNS, "2"), national_drug_code="ndc2", potency_unit_code="puc2"),
            Medication(id=uuid5(NAMESPACE_DNS, "3"), national_drug_code="ndc3", potency_unit_code="puc3"),
            Medication(id=uuid5(NAMESPACE_DNS, "4"), national_drug_code="ndc4", potency_unit_code="puc4"),
        ],
    ]

    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        MedicationCached(
            uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39",
            label="display1c",
            code_rx_norm="CODE123",
            code_fdb="CODE231",
            national_drug_code="ndc1",
            potency_unit_code="puc1",
        ),
        MedicationCached(
            uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a",
            label="display2a",
            code_rx_norm="CODE45",
            code_fdb="",
            national_drug_code="ndc2",
            potency_unit_code="puc2",
        ),
        MedicationCached(
            uuid="98123fde-012f-5ff3-8b50-881449dac91a",
            label="display3c",
            code_rx_norm="CODE9876",
            code_fdb="CODE8976",
            national_drug_code="ndc3",
            potency_unit_code="puc3",
        ),
        MedicationCached(
            uuid="6ed955c6-506a-5343-9be4-2c0afae02eef",
            label="display4c",
            code_rx_norm="",
            code_fdb="CODE5654",
            national_drug_code="ndc4",
            potency_unit_code="puc4",
        ),
    ]
    result = tested.current_medications()
    assert result == expected
    assert tested._medications == expected
    calls = [
        call.committed(),
        call.committed().for_patient('patientUuid'),
        call.committed().for_patient().filter(status="active"),
        call.committed().for_patient().filter().order_by('-dbid'),
    ]
    assert medication_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()

    result = tested.current_medications()
    assert result == expected
    assert tested._medications == expected
    assert medication_db.mock_calls == []
    assert codings_db.mock_calls == []
    reset_mocks()


@patch.object(AllergyIntolerance, 'codings')
@patch.object(AllergyIntolerance, 'objects')
def test_current_allergies(allergy_db, codings_db):
    def reset_mocks():
        allergy_db.reset_mock()
        codings_db.reset_mock()

    codings_db.all.side_effect = [
        [
            AllergyIntoleranceCoding(system="http://www.fdbhealth.com/", display="display1a", code="CODE123"),
            AllergyIntoleranceCoding(system="OTHER", display="display1b", code="CODE321"),
        ],
        [
            AllergyIntoleranceCoding(system="http://www.fdbhealth.com/", display="display2a", code="CODE45"),
            AllergyIntoleranceCoding(system="OTHER", display="display2b", code="CODE54"),
        ],
        [
            AllergyIntoleranceCoding(system="OTHER", display="display3b", code="CODE6789"),
            AllergyIntoleranceCoding(system="http://www.fdbhealth.com/", display="display3a", code="CODE9876"),
        ],
    ]
    allergy_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            AllergyIntolerance(id=uuid5(NAMESPACE_DNS, "1")),
            AllergyIntolerance(id=uuid5(NAMESPACE_DNS, "2")),
            AllergyIntolerance(id=uuid5(NAMESPACE_DNS, "3")),
        ],
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1a", code="CODE123"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2a", code="CODE45"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3a", code="CODE9876"),
    ]
    result = tested.current_allergies()
    assert result == expected
    assert tested._allergies == expected
    calls = [
        call.committed(),
        call.committed().for_patient('patientUuid'),
        call.committed().for_patient().filter(status="active"),
        call.committed().for_patient().filter().order_by('-dbid'),
    ]
    assert allergy_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()

    result = tested.current_allergies()
    assert result == expected
    assert tested._allergies == expected
    assert allergy_db.mock_calls == []
    assert codings_db.mock_calls == []
    reset_mocks()


def test_family_history():
    tested = LimitedCache("patientUuid", "providerUuid", {})
    result = tested.family_history()
    assert result == []
    assert tested._family_history == []

    result = tested.family_history()
    assert result == []
    assert tested._family_history == []


@patch.object(LimitedCache, 'retrieve_conditions')
def test_condition_history(retrieve_conditions):
    def reset_mocks():
        retrieve_conditions.reset_mock()

    tested = LimitedCache("patientUuid", "providerUuid", {})
    assert tested._condition_history is None
    result = tested.condition_history()
    assert result == []
    calls = [call()]
    assert retrieve_conditions.mock_calls == calls
    reset_mocks()

    tested._condition_history = []
    result = tested.condition_history()
    assert result == []
    assert tested._condition_history == []
    assert retrieve_conditions.mock_calls == []
    reset_mocks()


@patch.object(LimitedCache, 'retrieve_conditions')
def test_surgery_history(retrieve_conditions):
    def reset_mocks():
        retrieve_conditions.reset_mock()

    tested = LimitedCache("patientUuid", "providerUuid", {})
    assert tested._surgery_history is None
    result = tested.surgery_history()
    assert result == []
    calls = [call()]
    assert retrieve_conditions.mock_calls == calls
    reset_mocks()

    tested._surgery_history = []
    result = tested.surgery_history()
    assert result == []
    assert tested._surgery_history == []
    assert retrieve_conditions.mock_calls == []
    reset_mocks()


@patch.object(NoteType, 'objects')
def test_existing_note_types(note_type_db):
    def reset_mocks():
        note_type_db.reset_mock()

    note_type_db.filter.return_value.order_by.side_effect = [
        [
            NoteType(id=uuid5(NAMESPACE_DNS, "1"), name="noteType1", code="code1"),
            NoteType(id=uuid5(NAMESPACE_DNS, "2"), name="noteType2", code="code2"),
            NoteType(id=uuid5(NAMESPACE_DNS, "3"), name="noteType3", code="code3"),
        ],
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="noteType1", code="code1"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="noteType2", code="code2"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="noteType3", code="code3"),
    ]
    result = tested.existing_note_types()
    assert result == expected
    assert tested._note_type == expected
    calls = [
        call.filter(is_active=True, is_visible=True, is_scheduleable=True),
        call.filter().order_by('-dbid'),
    ]
    assert note_type_db.mock_calls == calls
    reset_mocks()

    result = tested.existing_note_types()
    assert result == expected
    assert tested._note_type == expected
    assert note_type_db.mock_calls == []
    reset_mocks()


@patch.object(ReasonForVisitSettingCoding, 'objects')
def test_existing_reason_for_visits(rfv_coding_db):
    def reset_mocks():
        rfv_coding_db.reset_mock()

    rfv_coding_db.order_by.side_effect = [
        [
            ReasonForVisitSettingCoding(id=uuid5(NAMESPACE_DNS, "1"), display="display1", code="code1"),
            ReasonForVisitSettingCoding(id=uuid5(NAMESPACE_DNS, "2"), display="display2", code="code2"),
            ReasonForVisitSettingCoding(id=uuid5(NAMESPACE_DNS, "3"), display="display3", code="code3"),
        ],
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1", code="code1"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2", code="code2"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3", code="code3"),
    ]
    result = tested.existing_reason_for_visits()
    assert result == expected
    assert tested._reason_for_visit == expected
    calls = [call.order_by('-dbid')]
    assert rfv_coding_db.mock_calls == calls
    reset_mocks()

    result = tested.existing_reason_for_visits()
    assert result == expected
    assert tested._reason_for_visit == expected
    assert rfv_coding_db.mock_calls == []
    reset_mocks()


@patch.object(Staff, 'objects')
def test_existing_staff_members(staff_db):
    def reset_mocks():
        staff_db.reset_mock()

    staff_db.filter.return_value.order_by.side_effect = [
        [
            Staff(dbid=1245, first_name="firstName1", last_name="lastName1"),
            Staff(dbid=1277, first_name="firstName2", last_name="lastName2"),
            Staff(dbid=1296, first_name="firstName3", last_name="lastName3"),
        ],
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        CodedItem(uuid="1245", label="firstName1 lastName1", code=""),
        CodedItem(uuid="1277", label="firstName2 lastName2", code=""),
        CodedItem(uuid="1296", label="firstName3 lastName3", code=""),
    ]
    result = tested.existing_staff_members()
    assert result == expected
    assert tested._staff_members == expected
    calls = [
        call.filter(active=True),
        call.filter().order_by('last_name'),
    ]
    assert staff_db.mock_calls == calls
    reset_mocks()

    result = tested.existing_staff_members()
    assert result == expected
    assert tested._staff_members == expected
    assert staff_db.mock_calls == []
    reset_mocks()


@patch.object(TaskLabel, 'objects')
def test_existing_task_labels(task_label_db):
    def reset_mocks():
        task_label_db.reset_mock()

    task_label_db.filter.return_value.order_by.side_effect = [
        [
            TaskLabel(dbid=1245, name="name1"),
            TaskLabel(dbid=1277, name="name2"),
            TaskLabel(dbid=1296, name="name3"),
        ],
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    expected = [
        CodedItem(uuid="1245", label="name1", code=""),
        CodedItem(uuid="1277", label="name2", code=""),
        CodedItem(uuid="1296", label="name3", code=""),
    ]
    result = tested.existing_task_labels()
    assert result == expected
    assert tested._task_labels == expected
    calls = [
        call.filter(active=True),
        call.filter().order_by('name'),
    ]
    assert task_label_db.mock_calls == calls
    reset_mocks()

    result = tested.existing_task_labels()
    assert result == expected
    assert tested._task_labels == expected
    assert task_label_db.mock_calls == []
    reset_mocks()


@patch('hyperscribe.libraries.limited_cache.date')
@patch.object(Observation, 'objects')
@patch.object(Patient, 'objects')
def test_demographic__str__(patient_db, observation_db, mock_date):
    def reset_mocks():
        patient_db.reset_mock()
        observation_db.reset_mock()
        mock_date.reset_mock()

    mock_date.today.return_value = date(2025, 2, 5)

    tests = [
        (
            "F",
            date(1941, 2, 7),
            False,
            "the patient is a elderly woman, born on February 07, 1941 (age 83) and weight 124.38 pounds"
        ),
        (
            "F",
            date(1941, 2, 7),
            True,
            "the patient is a elderly woman, born on <DOB REDACTED> (age 83) and weight 124.38 pounds"
        ),
        (
            "F",
            date(2000, 2, 7),
            False,
            "the patient is a woman, born on February 07, 2000 (age 24) and weight 124.38 pounds"
        ),
        (
            "F",
            date(2020, 2, 7),
            False,
            "the patient is a girl, born on February 07, 2020 (age 4) and weight 124.38 pounds"
        ),
        (
            "F",
            date(2024, 7, 2),
            False,
            "the patient is a baby girl, born on July 02, 2024 (age 7 months) and weight 124.38 pounds"
        ),
        (
            "O",
            date(1941, 2, 7),
            False,
            "the patient is a elderly man, born on February 07, 1941 (age 83) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2000, 2, 7),
            False,
            "the patient is a man, born on February 07, 2000 (age 24) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2020, 2, 7),
            False,
            "the patient is a boy, born on February 07, 2020 (age 4) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2024, 7, 2),
            False,
            "the patient is a baby boy, born on July 02, 2024 (age 7 months) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2024, 7, 2),
            True,
            "the patient is a baby boy, born on <DOB REDACTED> (age 7 months) and weight 124.38 pounds"
        ),
    ]

    for sex_at_birth, birth_date, obfuscate, expected in tests:
        patient_db.get.side_effect = [
            Patient(sex_at_birth=sex_at_birth, birth_date=birth_date)
        ]
        observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            Observation(units="oz", value="1990"),
        ]
        tested = LimitedCache("patientUuid", "providerUuid", {})

        result = tested.demographic__str__(obfuscate)
        assert result == expected, f" ---> {sex_at_birth} - {birth_date}"
        assert tested._demographic == expected
        calls = [call.get(id="patientUuid")]
        assert patient_db.mock_calls == calls
        calls = [
            call.for_patient("patientUuid"),
            call.for_patient().filter(name="weight", category="vital-signs"),
            call.for_patient().filter().order_by("-effective_datetime"),
            call.for_patient().filter().order_by().first(),
        ]
        assert observation_db.mock_calls == calls
        calls = [call.today()]
        assert mock_date.mock_calls == calls
        reset_mocks()

        result = tested.demographic__str__(obfuscate)
        assert result == expected, f" ---> {sex_at_birth} - {birth_date}"
        assert tested._demographic == expected
        assert patient_db.mock_calls == []
        assert observation_db.mock_calls == []
        assert mock_date.mock_calls == []
        reset_mocks()

    # no weight
    patient_db.get.side_effect = [
        Patient(sex_at_birth="F", birth_date=date(2000, 2, 7))
    ]
    observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
        None
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    result = tested.demographic__str__(False)
    expected = "the patient is a woman, born on February 07, 2000 (age 24)"
    assert result == expected
    assert tested._demographic == expected
    calls = [call.get(id="patientUuid")]
    assert patient_db.mock_calls == calls
    calls = [
        call.for_patient("patientUuid"),
        call.for_patient().filter(name="weight", category="vital-signs"),
        call.for_patient().filter().order_by("-effective_datetime"),
        call.for_patient().filter().order_by().first(),
    ]
    assert observation_db.mock_calls == calls
    calls = [call.today()]
    assert mock_date.mock_calls == calls
    reset_mocks()

    # weight as pounds
    patient_db.get.side_effect = [
        Patient(sex_at_birth="F", birth_date=date(2000, 2, 7))
    ]
    observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
        Observation(units="any", value="125"),
    ]
    tested = LimitedCache("patientUuid", "providerUuid", {})
    result = tested.demographic__str__(False)
    expected = "the patient is a woman, born on February 07, 2000 (age 24) and weight 125.00 pounds"
    assert result == expected
    assert tested._demographic == expected
    calls = [call.get(id="patientUuid")]
    assert patient_db.mock_calls == calls
    calls = [
        call.for_patient("patientUuid"),
        call.for_patient().filter(name="weight", category="vital-signs"),
        call.for_patient().filter().order_by("-effective_datetime"),
        call.for_patient().filter().order_by().first(),
    ]
    assert observation_db.mock_calls == calls
    calls = [call.today()]
    assert mock_date.mock_calls == calls
    reset_mocks()


@patch.object(PracticeLocation, 'settings')
@patch.object(PracticeLocation, 'objects')
@patch.object(Staff, 'objects')
def test_practice_setting(staff_db, practice_location_db, practice_settings_db):
    def reset_mocks():
        staff_db.reset_mock()
        practice_location_db.reset_mock()
        practice_settings_db.reset_mock()

    tested = LimitedCache("patientUuid", "providerUuid", {})

    # all good
    # -- provider has no primary practice
    tested._settings = {}
    for idx in range(3):
        staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=None)]
        practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
        practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [PracticeLocationSetting(value="theValue")]

        result = tested.practice_setting("theSetting")
        expected = "theValue"
        assert result == expected

        if idx > 0:
            assert staff_db.mock_calls == []
            assert practice_location_db.mock_calls == []
            assert practice_settings_db.mock_calls == []
        else:
            calls = [
                call.filter(id='providerUuid'),
                call.filter().first(),
            ]
            assert staff_db.mock_calls == calls
            calls = [
                call.order_by('dbid'),
                call.order_by().first(),
            ]
            assert practice_location_db.mock_calls == calls
            calls = [
                call.filter(name='theSetting'),
                call.filter().order_by('dbid'),
                call.filter().order_by().first(),
            ]
            assert practice_settings_db.mock_calls == calls
        reset_mocks()
    # -- provider has one primary practice
    tested._settings = {}
    for idx in range(3):
        staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=PracticeLocation(full_name="theLocation"))]
        practice_location_db.order_by.return_value.first.side_effect = []
        practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [PracticeLocationSetting(value="theValue")]

        result = tested.practice_setting("theSetting")
        expected = "theValue"
        assert result == expected

        if idx > 0:
            assert staff_db.mock_calls == []
            assert practice_location_db.mock_calls == []
            assert practice_settings_db.mock_calls == []
        else:
            calls = [
                call.filter(id='providerUuid'),
                call.filter().first(),
            ]
            assert staff_db.mock_calls == calls
            assert practice_location_db.mock_calls == []
            calls = [
                call.filter(name='theSetting'),
                call.filter().order_by('dbid'),
                call.filter().order_by().first(),
            ]
            assert practice_settings_db.mock_calls == calls
        reset_mocks()

    # no setting found
    tested._settings = {}
    for idx in range(3):
        staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=None)]
        practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
        practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [None]

        result = tested.practice_setting("theSetting")
        assert result is None

        if idx > 0:
            assert staff_db.mock_calls == []
            assert practice_location_db.mock_calls == []
            assert practice_settings_db.mock_calls == []
        else:
            calls = [
                call.filter(id='providerUuid'),
                call.filter().first(),
            ]
            assert staff_db.mock_calls == calls
            calls = [
                call.order_by('dbid'),
                call.order_by().first(),
            ]
            assert practice_location_db.mock_calls == calls
            calls = [
                call.filter(name='theSetting'),
                call.filter().order_by('dbid'),
                call.filter().order_by().first(),
            ]
            assert practice_settings_db.mock_calls == calls
        reset_mocks()

    # no practice found
    tested._settings = {}
    for idx in range(3):
        staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=None)]
        practice_location_db.order_by.return_value.first.side_effect = [None]
        practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = []

        result = tested.practice_setting("theSetting")
        assert result is None

        if idx > 0:
            assert staff_db.mock_calls == []
            assert practice_location_db.mock_calls == []
            assert practice_settings_db.mock_calls == []
        else:
            calls = [
                call.filter(id='providerUuid'),
                call.filter().first(),
            ]
            assert staff_db.mock_calls == calls
            calls = [
                call.order_by('dbid'),
                call.order_by().first(),
            ]
            assert practice_location_db.mock_calls == calls
            assert practice_settings_db.mock_calls == []
        reset_mocks()

    # no provider found
    tested._settings = {}
    for idx in range(3):
        staff_db.filter.return_value.first.side_effect = [None]
        practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
        practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [PracticeLocationSetting(value="theValue")]

        result = tested.practice_setting("theSetting")
        expected = "theValue"
        assert result == expected

        if idx > 0:
            assert staff_db.mock_calls == []
            assert practice_location_db.mock_calls == []
            assert practice_settings_db.mock_calls == []
        else:
            calls = [
                call.filter(id='providerUuid'),
                call.filter().first(),
            ]
            assert staff_db.mock_calls == calls
            calls = [
                call.order_by('dbid'),
                call.order_by().first(),
            ]
            assert practice_location_db.mock_calls == calls
            calls = [
                call.filter(name='theSetting'),
                call.filter().order_by('dbid'),
                call.filter().order_by().first(),
            ]
            assert practice_settings_db.mock_calls == calls
        reset_mocks()


@patch.object(LimitedCache, 'practice_setting')
@patch.object(LabPartner, "objects")
def test_preferred_lab_partner(lab_partner_db, practice_setting):
    def reset_mocks():
        lab_partner_db.reset_mock()
        practice_setting.reset_mock()

    tested = LimitedCache("patientUuid", "providerUuid", {})

    tests = [
        (None, CodedItem(uuid="", label="thePreferredLab", code="")),
        (LabPartner(id="uuidLab", name="theLabPartner"), CodedItem(uuid="uuidLab", label="thePreferredLab", code="")),
    ]

    for lab_partner, expected in tests:
        tested._preferred_lab_partner = None
        for i in range(3):
            lab_partner_db.filter.return_value.first.side_effect = [lab_partner]
            practice_setting.side_effect = ["thePreferredLab"]

            result = tested.preferred_lab_partner()
            assert result == expected

            if i > 0:
                assert lab_partner_db.mock_calls == []
                assert practice_setting.mock_calls == []
            else:
                calls = [
                    call.filter(name='thePreferredLab'),
                    call.filter().first(),
                ]
                assert lab_partner_db.mock_calls == calls
                calls = [call("preferredLabPartner")]
                assert practice_setting.mock_calls == calls
            reset_mocks()


@patch.object(LimitedCache, 'existing_staff_members')
@patch.object(LimitedCache, 'existing_task_labels')
@patch.object(LimitedCache, 'preferred_lab_partner')
@patch.object(LimitedCache, 'practice_setting')
@patch.object(LimitedCache, 'surgery_history')
@patch.object(LimitedCache, 'family_history')
@patch.object(LimitedCache, 'existing_reason_for_visits')
@patch.object(LimitedCache, 'existing_note_types')
@patch.object(LimitedCache, 'current_medications')
@patch.object(LimitedCache, 'current_goals')
@patch.object(LimitedCache, 'current_conditions')
@patch.object(LimitedCache, 'current_allergies')
@patch.object(LimitedCache, 'condition_history')
@patch.object(LimitedCache, 'charge_descriptions')
@patch.object(LimitedCache, 'demographic__str__')
def test_to_json(
        demographic,
        charge_descriptions,
        condition_history,
        current_allergies,
        current_conditions,
        current_goals,
        current_medications,
        existing_note_types,
        existing_reason_for_visits,
        family_history,
        surgery_history,
        practice_setting,
        preferred_lab_partner,
        existing_task_labels,
        existing_staff_members,
):
    def reset_mocks():
        demographic.reset_mock()
        charge_descriptions.reset_mock()
        condition_history.reset_mock()
        current_allergies.reset_mock()
        current_conditions.reset_mock()
        current_goals.reset_mock()
        current_medications.reset_mock()
        existing_note_types.reset_mock()
        existing_reason_for_visits.reset_mock()
        family_history.reset_mock()
        surgery_history.reset_mock()
        practice_setting.reset_mock()
        preferred_lab_partner.reset_mock()
        existing_task_labels.reset_mock()
        existing_staff_members.reset_mock()

    tested = LimitedCache(
        "patientUuid",
        "providerUuid",
        {
            "keyX": [CodedItem(code="code1", label="label1", uuid="uuid1")],
            "keyY": [],
            "keyZ": [
                CodedItem(code="code3", label="label3", uuid="uuid3"),
                CodedItem(code="code2", label="label2", uuid="uuid2"),
            ],
        },
    )

    for obfuscate in [True, False]:
        demographic.side_effect = ["theDemographic"]
        charge_descriptions.side_effect = [[
            ChargeDescription(short_name="shortName1", full_name="fullName1", cpt_code="code1"),
            ChargeDescription(short_name="shortName2", full_name="fullName2", cpt_code="code2"),
        ]]
        condition_history.side_effect = [[
            CodedItem(uuid="uuid002", label="label002", code="code002"),
            CodedItem(uuid="uuid102", label="label102", code="code102"),
        ]]
        current_allergies.side_effect = [[
            CodedItem(uuid="uuid003", label="label003", code="code003"),
            CodedItem(uuid="uuid103", label="label103", code="code103"),
        ]]
        current_conditions.side_effect = [[
            CodedItem(uuid="uuid004", label="label004", code="code004"),
            CodedItem(uuid="uuid104", label="label104", code="code104"),
        ]]
        current_goals.side_effect = [[
            CodedItem(uuid="uuid005", label="label005", code="code005"),
            CodedItem(uuid="uuid105", label="label105", code="code105"),
        ]]
        current_medications.side_effect = [[
            MedicationCached(
                uuid="uuid076",
                label="label076",
                code_rx_norm="code076",
                code_fdb="code987",
                national_drug_code="ndc12",
                potency_unit_code="puc78",
            ),
            MedicationCached(
                uuid="uuid176",
                label="label176",
                code_rx_norm="code176",
                code_fdb="code998",
                national_drug_code="ndc17",
                potency_unit_code="puc56",
            ),
        ]]
        existing_note_types.side_effect = [[
            CodedItem(uuid="uuid007", label="label007", code="code007"),
            CodedItem(uuid="uuid107", label="label107", code="code107"),
        ]]
        existing_reason_for_visits.side_effect = [[
            CodedItem(uuid="uuid009", label="label009", code="code009"),
            CodedItem(uuid="uuid109", label="label109", code="code109"),
        ]]
        family_history.side_effect = [[
            CodedItem(uuid="uuid010", label="label010", code="code010"),
            CodedItem(uuid="uuid110", label="label110", code="code110"),
        ]]
        surgery_history.side_effect = [[
            CodedItem(uuid="uuid011", label="label011", code="code011"),
            CodedItem(uuid="uuid111", label="label111", code="code111"),
        ]]
        existing_task_labels.side_effect = [[
            CodedItem(uuid="uuid091", label="label091", code="code091"),
            CodedItem(uuid="uuid191", label="label191", code="code191"),
        ]]
        existing_staff_members.side_effect = [[
            CodedItem(uuid="uuid037", label="label037", code="code037"),
            CodedItem(uuid="uuid137", label="label137", code="code137"),
        ]]
        practice_setting.side_effect = [
            "thePreferredLabPartner",
            "theServiceAreaZipCodes",
        ]
        preferred_lab_partner.side_effect = [
            CodedItem(uuid="theUuid", label="theLabel", code="theCode"),
        ]

        result = tested.to_json(obfuscate)
        expected = {
            'conditionHistory': [
                {'code': 'code002', 'label': 'label002', 'uuid': 'uuid002'},
                {'code': 'code102', 'label': 'label102', 'uuid': 'uuid102'},
            ],
            'currentAllergies': [
                {'code': 'code003', 'label': 'label003', 'uuid': 'uuid003'},
                {'code': 'code103', 'label': 'label103', 'uuid': 'uuid103'},
            ],
            'currentConditions': [
                {'code': 'code004', 'label': 'label004', 'uuid': 'uuid004'},
                {'code': 'code104', 'label': 'label104', 'uuid': 'uuid104'},
            ],
            'currentGoals': [
                {'code': 'code005', 'label': 'label005', 'uuid': 'uuid005'},
                {'code': 'code105', 'label': 'label105', 'uuid': 'uuid105'},
            ],
            'currentMedications': [
                {
                    "codeRxNorm": "code076",
                    "label": "label076",
                    "uuid": "uuid076",
                    "codeFdb": "code987",
                    "nationalDrugCode": "ndc12",
                    "potencyUnitCode": "puc78",
                },
                {
                    "codeRxNorm": "code176",
                    "label": "label176",
                    "uuid": "uuid176",
                    "codeFdb": "code998",
                    "nationalDrugCode": "ndc17",
                    "potencyUnitCode": "puc56",
                },
            ],
            'demographicStr': 'theDemographic',
            'existingNoteTypes': [
                {'code': 'code007', 'label': 'label007', 'uuid': 'uuid007'},
                {'code': 'code107', 'label': 'label107', 'uuid': 'uuid107'},
            ],
            'existingReasonForVisit': [
                {'code': 'code009', 'label': 'label009', 'uuid': 'uuid009'},
                {'code': 'code109', 'label': 'label109', 'uuid': 'uuid109'},
            ],
            'existingStaffMembers': [],
            'existingTaskLabels': [
                {'code': 'code091', 'label': 'label091', 'uuid': 'uuid091'},
                {'code': 'code191', 'label': 'label191', 'uuid': 'uuid191'},
            ],
            'familyHistory': [
                {'code': 'code010', 'label': 'label010', 'uuid': 'uuid010'},
                {'code': 'code110', 'label': 'label110', 'uuid': 'uuid110'},
            ],
            'stagedCommands': {
                'keyX': [
                    {'code': 'code1', 'label': 'label1', 'uuid': 'uuid1'},
                ],
                'keyY': [],
                'keyZ': [
                    {'code': 'code3', 'label': 'label3', 'uuid': 'uuid3'},
                    {'code': 'code2', 'label': 'label2', 'uuid': 'uuid2'},
                ],
            },
            'surgeryHistory': [
                {'code': 'code011', 'label': 'label011', 'uuid': 'uuid011'},
                {'code': 'code111', 'label': 'label111', 'uuid': 'uuid111'},
            ],
            'chargeDescriptions': [
                {'fullName': 'fullName1', 'shortName': 'shortName1', 'cptCode': 'code1'},
                {'fullName': 'fullName2', 'shortName': 'shortName2', 'cptCode': 'code2'},
            ],
            "settings": {
                "preferredLabPartner": "thePreferredLabPartner",
                "serviceAreaZipCodes": "theServiceAreaZipCodes",
            },
            "preferredLabPartner": {
                "uuid": "theUuid",
                "label": "theLabel",
                "code": "theCode",
            },
        }

        assert result == expected

        calls = [call(obfuscate)]
        assert demographic.mock_calls == calls
        calls = [call()]
        assert condition_history.mock_calls == calls
        assert current_allergies.mock_calls == calls
        assert current_conditions.mock_calls == calls
        assert current_goals.mock_calls == calls
        assert current_medications.mock_calls == calls
        assert existing_note_types.mock_calls == calls
        assert existing_reason_for_visits.mock_calls == calls
        assert existing_staff_members.mock_calls == []
        assert existing_task_labels.mock_calls == calls
        assert family_history.mock_calls == calls
        assert surgery_history.mock_calls == calls
        assert preferred_lab_partner.mock_calls == calls
        reset_mocks()


def test_load_from_json():
    tested = LimitedCache
    result = tested.load_from_json({
        "conditionHistory": [
            {"code": "code002", "label": "label002", "uuid": "uuid002"},
            {"code": "code102", "label": "label102", "uuid": "uuid102"},
        ],
        "currentAllergies": [
            {"code": "code003", "label": "label003", "uuid": "uuid003"},
            {"code": "code103", "label": "label103", "uuid": "uuid103"},
        ],
        "currentConditions": [
            {"code": "code004", "label": "label004", "uuid": "uuid004"},
            {"code": "code104", "label": "label104", "uuid": "uuid104"},
        ],
        "currentGoals": [
            {"code": "code005", "label": "label005", "uuid": "uuid005"},
            {"code": "code105", "label": "label105", "uuid": "uuid105"},
        ],
        "currentMedications": [
            {"code": "code006", "label": "label006", "uuid": "uuid006"},
            {"code": "code106", "label": "label106", "uuid": "uuid106"},
            {
                "codeRxNorm": "code076",
                "label": "label076",
                "uuid": "uuid076",
                "codeFdb": "code987",
                "nationalDrugCode": "ndc12",
                "potencyUnitCode": "puc78",
            },
            {
                "codeRxNorm": "code176",
                "label": "label176",
                "uuid": "uuid176",
                "codeFdb": "code998",
                "nationalDrugCode": "ndc17",
                "potencyUnitCode": "puc56",
            },
        ],
        "demographicStr": "theDemographic",
        "existingNoteTypes": [
            {"code": "code008", "label": "label008", "uuid": "uuid008"},
            {"code": "code108", "label": "label108", "uuid": "uuid108"},
        ],
        "existingReasonForVisit": [
            {"code": "code009", "label": "label009", "uuid": "uuid009"},
            {"code": "code109", "label": "label109", "uuid": "uuid109"},
        ],
        'existingStaffMembers': [
            {'code': 'code037', 'label': 'label037', 'uuid': 'uuid037'},
            {'code': 'code137', 'label': 'label137', 'uuid': 'uuid137'},
        ],
        'existingTaskLabels': [
            {'code': 'code091', 'label': 'label091', 'uuid': 'uuid091'},
            {'code': 'code191', 'label': 'label191', 'uuid': 'uuid191'},
        ],
        "familyHistory": [
            {"code": "code010", "label": "label010", "uuid": "uuid010"},
            {"code": "code110", "label": "label110", "uuid": "uuid110"},
        ],
        "stagedCommands": {
            "keyX": [
                {"code": "code1", "label": "label1", "uuid": "uuid1"},
            ],
            "keyY": [],
            "keyZ": [
                {"code": "code3", "label": "label3", "uuid": "uuid3"},
                {"code": "code2", "label": "label2", "uuid": "uuid2"},
            ],
        },
        "surgeryHistory": [
            {"code": "code011", "label": "label011", "uuid": "uuid011"},
            {"code": "code111", "label": "label111", "uuid": "uuid111"},
        ],
        "chargeDescriptions": [
            {"full_name": "fullName1", "short_name": "shortName1", "cpt_code": "code1"},
            {"fullName": "fullName2", "shortName": "shortName2", "cptCode": "code2"},
        ],
        "settings": {
            "preferredLabPartner": "thePreferredLabPartner",
            "serviceAreaZipCodes": "theServiceAreaZipCodes",
        },
        "preferredLabPartner": {
            "uuid": "theUuid",
            "label": "theLabel",
            "code": "theCode",
        },
    })

    assert result.patient_uuid == "_PatientUuid"
    assert result._staged_commands == {
        "keyX": [CodedItem(code="code1", label="label1", uuid="uuid1")],
        "keyY": [],
        "keyZ": [
            CodedItem(code="code3", label="label3", uuid="uuid3"),
            CodedItem(code="code2", label="label2", uuid="uuid2"),
        ],
    }
    assert result.demographic__str__(True) == "theDemographic"

    assert result.current_allergies() == [
        CodedItem(uuid="uuid003", label="label003", code="code003"),
        CodedItem(uuid="uuid103", label="label103", code="code103"),
    ]
    assert result.condition_history() == [
        CodedItem(uuid="uuid002", label="label002", code="code002"),
        CodedItem(uuid="uuid102", label="label102", code="code102"),
    ]
    assert result.current_conditions() == [
        CodedItem(uuid="uuid004", label="label004", code="code004"),
        CodedItem(uuid="uuid104", label="label104", code="code104"),
    ]
    assert result.family_history() == [
        CodedItem(uuid="uuid010", label="label010", code="code010"),
        CodedItem(uuid="uuid110", label="label110", code="code110"),
    ]
    assert result.current_goals() == [
        CodedItem(uuid="uuid005", label="label005", code="code005"),
        CodedItem(uuid="uuid105", label="label105", code="code105"),
    ]
    assert result.current_medications() == [
        MedicationCached(uuid="uuid006", label="label006", code_rx_norm="code006", code_fdb="", national_drug_code="", potency_unit_code=""),
        MedicationCached(uuid="uuid106", label="label106", code_rx_norm="code106", code_fdb="", national_drug_code="", potency_unit_code=""),
        MedicationCached(
            uuid="uuid076",
            label="label076",
            code_rx_norm="code076",
            code_fdb="code987",
            national_drug_code="ndc12",
            potency_unit_code="puc78",
        ),
        MedicationCached(
            uuid="uuid176",
            label="label176",
            code_rx_norm="code176",
            code_fdb="code998",
            national_drug_code="ndc17",
            potency_unit_code="puc56",
        ),
    ]
    assert result.existing_note_types() == [
        CodedItem(uuid="uuid008", label="label008", code="code008"),
        CodedItem(uuid="uuid108", label="label108", code="code108"),
    ]
    assert result.existing_reason_for_visits() == [
        CodedItem(uuid="uuid009", label="label009", code="code009"),
        CodedItem(uuid="uuid109", label="label109", code="code109"),
    ]
    assert result.existing_staff_members() == []
    assert result.existing_task_labels() == [
        CodedItem(uuid="uuid091", label="label091", code="code091"),
        CodedItem(uuid="uuid191", label="label191", code="code191"),
    ]
    assert result.surgery_history() == [
        CodedItem(uuid="uuid011", label="label011", code="code011"),
        CodedItem(uuid="uuid111", label="label111", code="code111"),
    ]
    assert result.charge_descriptions() == [
        ChargeDescription(short_name="shortName1", full_name="fullName1", cpt_code="code1"),
        ChargeDescription(short_name="shortName2", full_name="fullName2", cpt_code="code2"),
    ]
    assert result.practice_setting("preferredLabPartner") == "thePreferredLabPartner"
    assert result.practice_setting("serviceAreaZipCodes") == "theServiceAreaZipCodes"
    assert result.preferred_lab_partner() == CodedItem(uuid="theUuid", label="theLabel", code="theCode")
