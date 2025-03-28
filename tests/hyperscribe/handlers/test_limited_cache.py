from datetime import date
from unittest.mock import patch, call
from uuid import uuid5, NAMESPACE_DNS

from canvas_sdk.commands.constants import CodeSystems
from canvas_sdk.v1.data import (
    Command, Condition, ConditionCoding, MedicationCoding,
    Medication, AllergyIntolerance, AllergyIntoleranceCoding,
    Questionnaire, Patient, Observation, NoteType, ReasonForVisitSettingCoding)
from django.db.models.expressions import When, Value, Case

from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.structures.coded_item import CodedItem


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
    assert tested._questionnaires is None
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


@patch.object(Questionnaire, 'objects')
def test_existing_questionnaires(questionnaire_db):
    def reset_mocks():
        questionnaire_db.reset_mock()

    questionnaire_db.filter.return_value.order_by.side_effect = [
        [
            Questionnaire(id=uuid5(NAMESPACE_DNS, "1"), name="questionnaire1"),
            Questionnaire(id=uuid5(NAMESPACE_DNS, "2"), name="questionnaire2"),
            Questionnaire(id=uuid5(NAMESPACE_DNS, "3"), name="questionnaire3"),
        ],
    ]
    tested = LimitedCache("patientUuid", {})
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="questionnaire1", code=""),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="questionnaire2", code=""),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="questionnaire3", code=""),
    ]
    result = tested.existing_questionnaires()
    assert result == expected
    assert tested._questionnaires == expected
    calls = [
        call.filter(status="AC", can_originate_in_charting=True, use_case_in_charting="QUES"),
        call.filter().order_by('-dbid'),
    ]
    assert questionnaire_db.mock_calls == calls
    reset_mocks()

    result = tested.existing_questionnaires()
    assert result == expected
    assert tested._questionnaires == expected
    assert questionnaire_db.mock_calls == []
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
            "the patient is a elderly woman, born on February 07, 1941 (age 83) and weight 124.38 pounds"
        ),
        (
            "F",
            date(2000, 2, 7),
            "the patient is a woman, born on February 07, 2000 (age 24) and weight 124.38 pounds"
        ),
        (
            "F",
            date(2020, 2, 7),
            "the patient is a girl, born on February 07, 2020 (age 4) and weight 124.38 pounds"
        ),
        (
            "F",
            date(2024, 7, 2),
            "the patient is a baby girl, born on July 02, 2024 (age 7 months) and weight 124.38 pounds"
        ),
        (
            "O",
            date(1941, 2, 7),
            "the patient is a elderly man, born on February 07, 1941 (age 83) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2000, 2, 7),
            "the patient is a man, born on February 07, 2000 (age 24) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2020, 2, 7),
            "the patient is a boy, born on February 07, 2020 (age 4) and weight 124.38 pounds"
        ),
        (
            "O",
            date(2024, 7, 2),
            "the patient is a baby boy, born on July 02, 2024 (age 7 months) and weight 124.38 pounds"
        ),
    ]

    for sex_at_birth, birth_date, expected in tests:
        patient_db.get.side_effect = [
            Patient(sex_at_birth=sex_at_birth, birth_date=birth_date)
        ]
        observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            Observation(units="oz", value="1990"),
        ]
        tested = LimitedCache("patientUuid", {})

        result = tested.demographic__str__()
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

        result = tested.demographic__str__()
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
    result = tested.demographic__str__()
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
    result = tested.demographic__str__()
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
