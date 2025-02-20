from datetime import date
from unittest.mock import patch, call
from uuid import uuid5, NAMESPACE_DNS

import pytest
from canvas_sdk.v1.data import Command, Condition, ConditionCoding, MedicationCoding, Medication, AllergyIntolerance, AllergyIntoleranceCoding, \
    Questionnaire, Patient, Observation, NoteType

from commander.protocols.commands.base import Base
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Base:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Base(settings, "patientUuid", "noteUuid", "providerUuid")


def test___init__():
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    tested = Base(settings, "patientUuid", "noteUuid", "providerUuid")
    assert tested.settings == settings
    assert tested.patient_uuid == "patientUuid"
    assert tested.note_uuid == "noteUuid"
    assert tested.provider_uuid == "providerUuid"
    assert tested._allergies is None
    assert tested._condition_history is None
    assert tested._conditions is None
    assert tested._demographic is None
    assert tested._family_history is None
    assert tested._goals is None
    assert tested._medications is None
    assert tested._note_type is None
    assert tested._questionnaires is None
    assert tested._surgery_history is None


def test_class_name():
    tested = Base
    result = tested.class_name()
    expected = "Base"
    assert result == expected


def test_schema_key():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.schema_key()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_command_from_json():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.command_from_json({})
    expected = "NotImplementedError"
    assert e.typename == expected


def test_command_parameters():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.command_parameters()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_instruction_description():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.instruction_description()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_instruction_constraints():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.instruction_constraints()
    expected = "NotImplementedError"
    assert e.typename == expected


def test_is_available():
    tested = helper_instance()
    with pytest.raises(Exception) as e:
        _ = tested.is_available()
    expected = "NotImplementedError"
    assert e.typename == expected


@patch.object(Command, 'objects')
def test_current_goals(command_db):
    def reset_mocks():
        command_db.reset_mock()

    command_db.filter.return_value.order_by.side_effect = [[
        Command(id=uuid5(NAMESPACE_DNS, "1"), dbid=258, data={"goal_statement": "statement1"}),
        Command(id=uuid5(NAMESPACE_DNS, "2"), dbid=259, data={"goal_statement": "statement2"}),
        Command(id=uuid5(NAMESPACE_DNS, "3"), dbid=267, data={"goal_statement": "statement3"}),
    ]]
    tested = helper_instance()
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


@patch.object(Condition, 'codings')
@patch.object(Condition, 'objects')
def test_current_conditions(condition_db, codings_db):
    def reset_mocks():
        condition_db.reset_mock()
        codings_db.reset_mock()

    codings_db.all.side_effect = [
        [
            ConditionCoding(system="ICD-10", display="display1a", code="CODE123"),
            ConditionCoding(system="OTHER", display="display1b", code="CODE321"),
        ],
        [
            ConditionCoding(system="ICD-10", display="display2a", code="CODE45"),
            ConditionCoding(system="OTHER", display="display2b", code="CODE54"),
        ],
        [
            ConditionCoding(system="OTHER", display="display3b", code="CODE6789"),
            ConditionCoding(system="ICD-10", display="display3a", code="CODE9876"),
        ],
    ]
    condition_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Condition(id=uuid5(NAMESPACE_DNS, "1")),
            Condition(id=uuid5(NAMESPACE_DNS, "2")),
            Condition(id=uuid5(NAMESPACE_DNS, "3")),
        ],
    ]
    tested = helper_instance()
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1a", code="CODE12.3"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2a", code="CODE45"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3a", code="CODE98.76"),
    ]
    result = tested.current_conditions()
    assert result == expected
    assert tested._conditions == expected
    calls = [
        call.committed(),
        call.committed().for_patient('patientUuid'),
        call.committed().for_patient().filter(clinical_status="active"),
        call.committed().for_patient().filter().order_by('-dbid'),
    ]
    assert condition_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()

    result = tested.current_conditions()
    assert result == expected
    assert tested._conditions == expected
    assert condition_db.mock_calls == []
    assert codings_db.mock_calls == []
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
    tested = helper_instance()
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
    tested = helper_instance()
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
    tested = helper_instance()
    result = tested.family_history()
    assert result == []
    assert tested._family_history == []

    result = tested.family_history()
    assert result == []
    assert tested._family_history == []


@patch.object(Condition, 'codings')
@patch.object(Condition, 'objects')
def test_condition_history(condition_db, codings_db):
    def reset_mocks():
        condition_db.reset_mock()
        codings_db.reset_mock()

    codings_db.all.side_effect = [
        [
            ConditionCoding(system="ICD-10", display="display1a", code="CODE123"),
            ConditionCoding(system="OTHER", display="display1b", code="CODE321"),
        ],
        [
            ConditionCoding(system="ICD-10", display="display2a", code="CODE45"),
            ConditionCoding(system="OTHER", display="display2b", code="CODE54"),
        ],
        [
            ConditionCoding(system="OTHER", display="display3b", code="CODE6789"),
            ConditionCoding(system="ICD-10", display="display3a", code="CODE9876"),
        ],
    ]
    condition_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Condition(id=uuid5(NAMESPACE_DNS, "1")),
            Condition(id=uuid5(NAMESPACE_DNS, "2")),
            Condition(id=uuid5(NAMESPACE_DNS, "3")),
        ],
    ]
    tested = helper_instance()
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1a", code="CODE12.3"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2a", code="CODE45"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3a", code="CODE98.76"),
    ]
    result = tested.condition_history()
    assert result == expected
    assert tested._condition_history == expected
    calls = [
        call.committed(),
        call.committed().for_patient('patientUuid'),
        call.committed().for_patient().filter(clinical_status="resolved"),
        call.committed().for_patient().filter().order_by('-dbid'),
    ]
    assert condition_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()

    result = tested.condition_history()
    assert result == expected
    assert tested._condition_history == expected
    assert condition_db.mock_calls == []
    assert codings_db.mock_calls == []
    reset_mocks()


@patch.object(Condition, 'codings')
@patch.object(Condition, 'objects')
def test_surgery_history(condition_db, codings_db):
    def reset_mocks():
        condition_db.reset_mock()
        codings_db.reset_mock()

    codings_db.all.side_effect = [
        [
            ConditionCoding(system="ICD-10", display="display1a", code="CODE123"),
            ConditionCoding(system="OTHER", display="display1b", code="CODE321"),
        ],
        [
            ConditionCoding(system="ICD-10", display="display2a", code="CODE45"),
            ConditionCoding(system="OTHER", display="display2b", code="CODE54"),
        ],
        [
            ConditionCoding(system="OTHER", display="display3b", code="CODE6789"),
            ConditionCoding(system="ICD-10", display="display3a", code="CODE9876"),
        ],
    ]
    condition_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Condition(id=uuid5(NAMESPACE_DNS, "1")),
            Condition(id=uuid5(NAMESPACE_DNS, "2")),
            Condition(id=uuid5(NAMESPACE_DNS, "3")),
        ],
    ]
    tested = helper_instance()
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1a", code="CODE12.3"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2a", code="CODE45"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3a", code="CODE98.76"),
    ]
    result = tested.surgery_history()
    assert result == expected
    assert tested._surgery_history == expected
    calls = [
        call.committed(),
        call.committed().for_patient('patientUuid'),
        call.committed().for_patient().filter(clinical_status="resolved"),
        call.committed().for_patient().filter().order_by('-dbid'),
    ]
    assert condition_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()

    result = tested.surgery_history()
    assert result == expected
    assert tested._surgery_history == expected
    assert condition_db.mock_calls == []
    assert codings_db.mock_calls == []
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
    tested = helper_instance()
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
    tested = helper_instance()
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


@patch('commander.protocols.commands.base.date')
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
        tested = helper_instance()

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
    tested = helper_instance()
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
    tested = helper_instance()
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
