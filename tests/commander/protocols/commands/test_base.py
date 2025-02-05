from datetime import date
from unittest.mock import patch, call
from uuid import uuid5, NAMESPACE_DNS

import pytest
from canvas_sdk.v1.data import Command, Condition, ConditionCoding, MedicationCoding, Medication, AllergyIntolerance, AllergyIntoleranceCoding, \
    Questionnaire, Patient, Observation

from commander.protocols.commands.base import Base
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> Base:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Base(settings, "patientUuid", "noteUuid", "providerUuid")


def test___init__():
    settings = Settings(
        openai_key="openaiKey",
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


@patch('commander.protocols.commands.base.Command.objects')
def test_current_goals(command):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        command.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.current_goals()
        assert result == []
        assert tested._goals is None
        assert command.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        command.filter.return_value.order_by.side_effect = [[
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
        assert command.mock_calls == calls
        reset_mocks()

        result = tested.current_goals()
        assert result == expected
        assert tested._goals == expected
        assert command.mock_calls == []
        reset_mocks()


@patch('commander.protocols.commands.base.Condition.codings')
@patch('commander.protocols.commands.base.Condition.objects')
def test_current_conditions(condition, codings):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        condition.reset_mock()
        codings.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.current_conditions()
        assert result == []
        assert tested._conditions is None
        assert condition.mock_calls == []
        for coding in codings:
            assert coding.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        codings.all.side_effect = [
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
        condition.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
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
        assert condition.mock_calls == calls
        calls = [call.all(), call.all(), call.all()]
        assert codings.mock_calls == calls
        reset_mocks()

        result = tested.current_conditions()
        assert result == expected
        assert tested._conditions == expected
        assert condition.mock_calls == []
        assert codings.mock_calls == []
        reset_mocks()


@patch('commander.protocols.commands.base.Medication.codings')
@patch('commander.protocols.commands.base.Medication.objects')
def test_current_medications(medication, codings):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        medication.reset_mock()
        codings.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.current_medications()
        assert result == []
        assert tested._medications is None
        assert medication.mock_calls == []
        for coding in codings:
            assert coding.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        codings.all.side_effect = [
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
        medication.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
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
        assert medication.mock_calls == calls
        calls = [call.all(), call.all(), call.all()]
        assert codings.mock_calls == calls
        reset_mocks()

        result = tested.current_medications()
        assert result == expected
        assert tested._medications == expected
        assert medication.mock_calls == []
        assert codings.mock_calls == []
        reset_mocks()


@patch('commander.protocols.commands.base.AllergyIntolerance.codings')
@patch('commander.protocols.commands.base.AllergyIntolerance.objects')
def test_current_allergies(allergy, codings):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        allergy.reset_mock()
        codings.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.current_allergies()
        assert result == []
        assert tested._allergies is None
        assert allergy.mock_calls == []
        for coding in codings:
            assert coding.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        codings.all.side_effect = [
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
        allergy.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
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
        assert allergy.mock_calls == calls
        calls = [call.all(), call.all(), call.all()]
        assert codings.mock_calls == calls
        reset_mocks()

        result = tested.current_allergies()
        assert result == expected
        assert tested._allergies == expected
        assert allergy.mock_calls == []
        assert codings.mock_calls == []
        reset_mocks()


def test_family_history():
    # TODO to adapt when access to the database is available
    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.family_history()
        assert result == []
        assert tested._family_history is None

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        tested = helper_instance()
        result = tested.family_history()
        assert result == []
        assert tested._family_history == []

        result = tested.family_history()
        assert result == []
        assert tested._family_history == []


@patch('commander.protocols.commands.base.Condition.codings')
@patch('commander.protocols.commands.base.Condition.objects')
def test_condition_history(condition, codings):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        condition.reset_mock()
        codings.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.condition_history()
        assert result == []
        assert tested._condition_history is None
        assert condition.mock_calls == []
        for coding in codings:
            assert coding.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        codings.all.side_effect = [
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
        condition.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
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
        assert condition.mock_calls == calls
        calls = [call.all(), call.all(), call.all()]
        assert codings.mock_calls == calls
        reset_mocks()

        result = tested.condition_history()
        assert result == expected
        assert tested._condition_history == expected
        assert condition.mock_calls == []
        assert codings.mock_calls == []
        reset_mocks()


@patch('commander.protocols.commands.base.Condition.codings')
@patch('commander.protocols.commands.base.Condition.objects')
def test_surgery_history(condition, codings):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        condition.reset_mock()
        codings.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.surgery_history()
        assert result == []
        assert tested._surgery_history is None
        assert condition.mock_calls == []
        for coding in codings:
            assert coding.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        codings.all.side_effect = [
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
        condition.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
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
        assert condition.mock_calls == calls
        calls = [call.all(), call.all(), call.all()]
        assert codings.mock_calls == calls
        reset_mocks()

        result = tested.surgery_history()
        assert result == expected
        assert tested._surgery_history == expected
        assert condition.mock_calls == []
        assert codings.mock_calls == []
        reset_mocks()


@patch('commander.protocols.commands.base.Questionnaire.objects')
def test_existing_questionnaires(questionnaire):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        questionnaire.reset_mock()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.existing_questionnaires()
        assert result == []
        assert tested._questionnaires is None
        assert questionnaire.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
        questionnaire.filter.return_value.order_by.side_effect = [
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
        assert questionnaire.mock_calls == calls
        reset_mocks()

        result = tested.existing_questionnaires()
        assert result == expected
        assert tested._questionnaires == expected
        assert questionnaire.mock_calls == []
        reset_mocks()


@patch('commander.protocols.commands.base.date')
@patch('commander.protocols.commands.base.Observation.objects')
@patch('commander.protocols.commands.base.Patient.objects')
def test_demographic__str__(patient, observation, mock_date):
    # TODO to adapt when access to the database is available
    def reset_mocks():
        patient.reset_mock()
        observation.reset_mock()
        mock_date.reset_mock()

    mock_date.today.return_value = date(2025, 2, 5)

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', False):
        tested = helper_instance()
        result = tested.demographic__str__()
        expected = "the patient is a man, born on April 17, 2001 (age 23) and weight 150.00 pounds"
        assert result == expected
        assert patient.mock_calls == []
        assert observation.mock_calls == []
        assert mock_date.mock_calls == []
        reset_mocks()

    with patch('commander.protocols.constants.Constants.HAS_DATABASE_ACCESS', True):
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
            patient.get.side_effect = [
                Patient(sex_at_birth=sex_at_birth, birth_date=birth_date)
            ]
            observation.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
                Observation(units="oz", value="1990"),
            ]
            tested = helper_instance()

            result = tested.demographic__str__()
            assert result == expected, f" ---> {sex_at_birth} - {birth_date}"
            assert tested._demographic == expected
            calls = [call.get(id="patientUuid")]
            assert patient.mock_calls == calls
            calls = [
                call.for_patient("patientUuid"),
                call.for_patient().filter(name="weight", category="vital-signs"),
                call.for_patient().filter().order_by("-effective_datetime"),
                call.for_patient().filter().order_by().first(),
            ]
            assert observation.mock_calls == calls
            calls = [call.today()]
            assert mock_date.mock_calls == calls
            reset_mocks()

            result = tested.demographic__str__()
            assert result == expected, f" ---> {sex_at_birth} - {birth_date}"
            assert tested._demographic == expected
            assert patient.mock_calls == []
            assert observation.mock_calls == []
            assert mock_date.mock_calls == []
            reset_mocks()

        # no weight
        patient.get.side_effect = [
            Patient(sex_at_birth="F", birth_date=date(2000, 2, 7))
        ]
        observation.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            None
        ]
        tested = helper_instance()
        result = tested.demographic__str__()
        expected = "the patient is a woman, born on February 07, 2000 (age 24)"
        assert result == expected
        assert tested._demographic == expected
        calls = [call.get(id="patientUuid")]
        assert patient.mock_calls == calls
        calls = [
            call.for_patient("patientUuid"),
            call.for_patient().filter(name="weight", category="vital-signs"),
            call.for_patient().filter().order_by("-effective_datetime"),
            call.for_patient().filter().order_by().first(),
        ]
        assert observation.mock_calls == calls
        calls = [call.today()]
        assert mock_date.mock_calls == calls
        reset_mocks()

        # weight as pounds
        patient.get.side_effect = [
            Patient(sex_at_birth="F", birth_date=date(2000, 2, 7))
        ]
        observation.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            Observation(units="any", value="125"),
        ]
        tested = helper_instance()
        result = tested.demographic__str__()
        expected = "the patient is a woman, born on February 07, 2000 (age 24) and weight 125.00 pounds"
        assert result == expected
        assert tested._demographic == expected
        calls = [call.get(id="patientUuid")]
        assert patient.mock_calls == calls
        calls = [
            call.for_patient("patientUuid"),
            call.for_patient().filter(name="weight", category="vital-signs"),
            call.for_patient().filter().order_by("-effective_datetime"),
            call.for_patient().filter().order_by().first(),
        ]
        assert observation.mock_calls == calls
        calls = [call.today()]
        assert mock_date.mock_calls == calls
        reset_mocks()
