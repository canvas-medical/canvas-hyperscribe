from datetime import date
from unittest.mock import patch, call
from uuid import uuid5, NAMESPACE_DNS

from canvas_sdk.commands.constants import CodeSystems
from canvas_sdk.v1.data import (
    Command, Condition, ConditionCoding, MedicationCoding,
    Medication, AllergyIntolerance, AllergyIntoleranceCoding,
    Patient, Observation, NoteType, ReasonForVisitSettingCoding)
from django.db.models.expressions import When, Value, Case

from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction import Instruction


def test___init__():
    staged_commands_to_coded_items = {
        "keyX": [CodedItem(code="code1", label="label1", uuid="uuid1")],
        "keyY": [],
        "keyZ": [
            CodedItem(code="code3", label="label3", uuid="uuid3"),
            CodedItem(code="code2", label="label2", uuid="uuid2"),
        ],
    }
    tested = LimitedCache("patientUuid", staged_commands_to_coded_items)
    assert tested.patient_uuid == "patientUuid"
    assert tested._allergies is None
    assert tested._condition_history is None
    assert tested._conditions is None
    assert tested._demographic is None
    assert tested._family_history is None
    assert tested._goals is None
    assert tested._medications is None
    assert tested._note_type is None
    assert tested._reason_for_visit is None
    assert tested._surgery_history is None
    assert tested._staged_commands == staged_commands_to_coded_items


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
    tested = LimitedCache("patientUuid", {})
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
    tested = LimitedCache("patientUuid", staged_commands_to_coded_items)

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
    tested = LimitedCache("patientUuid", staged_commands_to_coded_items)

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
    tested = LimitedCache("patientUuid", {})
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

    tested = LimitedCache("patientUuid", {})
    assert tested._conditions is None
    result = tested.current_conditions()
    assert result is None
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

    codings_db.all.side_effect = [
        [
            MedicationCoding(system="http://www.nlm.nih.gov/research/umls/rxnorm", display="display1a", code="CODE123"),
            MedicationCoding(system="OTHER", display="display1b", code="CODE321"),
        ],
        [
            MedicationCoding(system="http://www.nlm.nih.gov/research/umls/rxnorm", display="display2a", code="CODE45"),
            MedicationCoding(system="OTHER", display="display2b", code="CODE54"),
        ],
        [
            MedicationCoding(system="OTHER", display="display3b", code="CODE6789"),
            MedicationCoding(system="http://www.nlm.nih.gov/research/umls/rxnorm", display="display3a", code="CODE9876"),
        ],
    ]
    medication_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Medication(id=uuid5(NAMESPACE_DNS, "1")),
            Medication(id=uuid5(NAMESPACE_DNS, "2")),
            Medication(id=uuid5(NAMESPACE_DNS, "3")),
        ],
    ]
    tested = LimitedCache("patientUuid", {})
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1a", code="CODE123"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2a", code="CODE45"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3a", code="CODE9876"),
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
    calls = [call.all(), call.all(), call.all()]
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
    tested = LimitedCache("patientUuid", {})
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
    tested = LimitedCache("patientUuid", {})
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

    tested = LimitedCache("patientUuid", {})
    assert tested._condition_history is None
    result = tested.condition_history()
    assert result is None
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

    tested = LimitedCache("patientUuid", {})
    assert tested._surgery_history is None
    result = tested.surgery_history()
    assert result is None
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
    tested = LimitedCache("patientUuid", {})
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
    tested = LimitedCache("patientUuid", {})
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


@patch('hyperscribe.handlers.limited_cache.date')
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
        tested = LimitedCache("patientUuid", {})

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
    tested = LimitedCache("patientUuid", {})
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
    tested = LimitedCache("patientUuid", {})
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


@patch.object(LimitedCache, 'surgery_history')
@patch.object(LimitedCache, 'family_history')
@patch.object(LimitedCache, 'existing_reason_for_visits')
@patch.object(LimitedCache, 'existing_note_types')
@patch.object(LimitedCache, 'current_medications')
@patch.object(LimitedCache, 'current_goals')
@patch.object(LimitedCache, 'current_conditions')
@patch.object(LimitedCache, 'current_allergies')
@patch.object(LimitedCache, 'condition_history')
@patch.object(LimitedCache, 'demographic__str__')
def test_to_json(
        demographic,
        condition_history,
        current_allergies,
        current_conditions,
        current_goals,
        current_medications,
        existing_note_types,
        existing_reason_for_visits,
        family_history,
        surgery_history,
):
    def reset_mocks():
        demographic.reset_mock()
        condition_history.reset_mock()
        current_allergies.reset_mock()
        current_conditions.reset_mock()
        current_goals.reset_mock()
        current_medications.reset_mock()
        existing_note_types.reset_mock()
        existing_reason_for_visits.reset_mock()
        family_history.reset_mock()
        surgery_history.reset_mock()

    tested = LimitedCache(
        "patientUuid",
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
            CodedItem(uuid="uuid006", label="label006", code="code006"),
            CodedItem(uuid="uuid106", label="label106", code="code106"),
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
                {'code': 'code006', 'label': 'label006', 'uuid': 'uuid006'},
                {'code': 'code106', 'label': 'label106', 'uuid': 'uuid106'},
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
        assert family_history.mock_calls == calls
        assert surgery_history.mock_calls == calls
        reset_mocks()


def test_load_from_json():
    tested = LimitedCache
    result = tested.load_from_json({
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
            {'code': 'code006', 'label': 'label006', 'uuid': 'uuid006'},
            {'code': 'code106', 'label': 'label106', 'uuid': 'uuid106'},
        ],
        'demographicStr': 'theDemographic',
        'existingNoteTypes': [
            {'code': 'code008', 'label': 'label008', 'uuid': 'uuid008'},
            {'code': 'code108', 'label': 'label108', 'uuid': 'uuid108'},
        ],
        'existingReasonForVisit': [
            {'code': 'code009', 'label': 'label009', 'uuid': 'uuid009'},
            {'code': 'code109', 'label': 'label109', 'uuid': 'uuid109'},
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
        CodedItem(uuid="uuid006", label="label006", code="code006"),
        CodedItem(uuid="uuid106", label="label106", code="code106"),
    ]
    assert result.existing_note_types() == [
        CodedItem(uuid="uuid008", label="label008", code="code008"),
        CodedItem(uuid="uuid108", label="label108", code="code108"),
    ]
    assert result.existing_reason_for_visits() == [
        CodedItem(uuid="uuid009", label="label009", code="code009"),
        CodedItem(uuid="uuid109", label="label109", code="code109"),
    ]
    assert result.surgery_history() == [
        CodedItem(uuid="uuid011", label="label011", code="code011"),
        CodedItem(uuid="uuid111", label="label111", code="code111"),
    ]
