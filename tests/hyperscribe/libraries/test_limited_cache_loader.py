from datetime import date, datetime, timezone
from unittest.mock import patch, call, MagicMock, PropertyMock
from uuid import uuid5, NAMESPACE_DNS

from canvas_sdk.commands.constants import CodeSystems
from canvas_sdk.test_utils import factories
from canvas_sdk.v1.data import (
    CareTeamRole,
    ChargeDescriptionMaster,
    Condition,
    ConditionCoding,
    Goal,
    Immunization,
    ImmunizationCoding,
    ImmunizationStatement,
    ImmunizationStatementCoding,
    MedicationCoding,
    Medication,
    AllergyIntolerance,
    AllergyIntoleranceCoding,
    Observation,
    Note,
    NoteType,
    ReasonForVisitSettingCoding,
    Staff,
    StaffRole,
    PracticeLocation,
    PracticeLocationSetting,
    TaskLabel,
    Team,
)
from canvas_sdk.v1.data import Command
from canvas_sdk.v1.data.goal import GoalLifecycleStatus
from canvas_sdk.v1.data.lab import LabPartner
from django.db.models.expressions import When, Value, Case

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.limited_cache_loader import LimitedCacheLoader
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.charge_description import ChargeDescription
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.immunization_cached import ImmunizationCached
from hyperscribe.structures.medication_cached import MedicationCached


def helper_instance(patient_uuid="patientUuid", obfuscate=False) -> LimitedCacheLoader:
    identification = IdentificationParameters(
        patient_uuid=patient_uuid,
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    policy = AccessPolicy(policy=True, items=["item1", "item2", "item3"])
    return LimitedCacheLoader(identification, policy, obfuscate)


def test___init__():
    identification = IdentificationParameters(
        patient_uuid="patientId",
        note_uuid="noteId",
        provider_uuid="theProviderId",
        canvas_instance="customerIdentifier",
    )
    policy = AccessPolicy(policy=True, items=["item1", "item2", "item3"])
    tested = LimitedCacheLoader(identification, policy, True)
    assert tested.identification is identification
    assert tested.commands_policy is policy
    assert tested.obfuscate is True


@patch.object(ImplementedCommands, "command_list")
def test_commands_to_coded_items(command_list):
    mock_commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        command_list.reset_mock()
        for c in mock_commands:
            c.reset_mock()

    tested = LimitedCacheLoader
    current_commands = [
        Command(id="uuid1", schema_key="canvas_command_X", data={"key1": "value1"}),
        Command(id="uuid2", schema_key="canvas_command_X", data={"key2": "value2"}),
        Command(id="uuid3", schema_key="canvas_command_Y", data={"key3": "value3"}),
        Command(id="uuid4", schema_key="canvas_command_Y", data={"key4": "value4"}),
        Command(id="uuid5", schema_key="canvas_command_Y", data={"key5": "value5"}),
        Command(id="uuid6", schema_key="canvas_command_A", data={"key6": "value6"}),
    ]

    # all commands allowed
    command_list.side_effect = [mock_commands] * 6

    mock_commands[0].schema_key.return_value = "canvas_command_X"
    mock_commands[0].class_name.return_value = "CommandX"
    mock_commands[1].schema_key.return_value = "canvas_command_Y"
    mock_commands[1].class_name.return_value = "CommandY"
    mock_commands[2].schema_key.return_value = "canvas_command_Z"
    mock_commands[2].class_name.return_value = "CommandZ"

    mock_commands[0].staged_command_extract.side_effect = [CodedItem(label="label1", code="code1", uuid=""), None]
    mock_commands[1].staged_command_extract.side_effect = [
        CodedItem(label="label3", code="code3", uuid=""),
        CodedItem(label="label4", code="code4", uuid=""),
        CodedItem(label="label5", code="code5", uuid=""),
    ]
    mock_commands[2].staged_command_extract.side_effect = []

    policy = AccessPolicy(policy=True, items=["CommandX", "CommandY", "CommandZ"])
    result = tested.commands_to_coded_items(current_commands, policy, True)
    expected = {
        "canvas_command_X": [CodedItem(uuid="uuid1", label="label1", code="code1")],
        "canvas_command_Y": [
            CodedItem(uuid="uuid3", label="label3", code="code3"),
            CodedItem(uuid="uuid4", label="label4", code="code4"),
            CodedItem(uuid="uuid5", label="label5", code="code5"),
        ],
    }
    assert result == expected
    calls = [call()] * 6
    assert command_list.mock_calls == calls
    calls = [
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key1": "value1"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key2": "value2"}),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
    ]
    assert mock_commands[0].mock_calls == calls
    calls = [
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key3": "value3"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key4": "value4"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key5": "value5"}),
        call.class_name(),
        call.schema_key(),
    ]
    assert mock_commands[1].mock_calls == calls
    calls = [call.class_name(), call.schema_key()]
    assert mock_commands[2].mock_calls == calls
    reset_mocks()

    # one command allowed
    command_list.side_effect = [mock_commands] * 6

    mock_commands[0].schema_key.return_value = "canvas_command_X"
    mock_commands[0].class_name.return_value = "CommandX"
    mock_commands[1].schema_key.return_value = "canvas_command_Y"
    mock_commands[1].class_name.return_value = "CommandY"
    mock_commands[2].schema_key.return_value = "canvas_command_Z"
    mock_commands[2].class_name.return_value = "CommandZ"

    mock_commands[0].staged_command_extract.side_effect = [CodedItem(label="label1", code="code1", uuid=""), None]
    mock_commands[1].staged_command_extract.side_effect = [
        CodedItem(label="label3", code="code3", uuid=""),
        CodedItem(label="label4", code="code4", uuid=""),
        CodedItem(label="label5", code="code5", uuid=""),
    ]
    mock_commands[2].staged_command_extract.side_effect = []

    policy = AccessPolicy(policy=True, items=["CommandX"])
    result = tested.commands_to_coded_items(current_commands, policy, False)
    expected = {"canvas_command_X": [CodedItem(uuid="", label="label1", code="code1")]}
    assert result == expected
    calls = [call()] * 6
    assert command_list.mock_calls == calls
    calls = [
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key1": "value1"}),
        call.class_name(),
        call.schema_key(),
        call.staged_command_extract({"key2": "value2"}),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
        call.class_name(),
        call.schema_key(),
    ]
    assert mock_commands[0].mock_calls == calls
    calls = [call.class_name(), call.class_name(), call.class_name(), call.class_name()]
    assert mock_commands[1].mock_calls == calls
    assert mock_commands[2].mock_calls == calls
    reset_mocks()


@patch.object(Command, "objects")
def test_current_commands(command_db):
    def reset_mocks():
        command_db.reset_mock()

    command_db.filter.return_value.order_by.side_effect = [["command1", "command2", "command3"]]
    tested = helper_instance()
    result = tested.current_commands()
    expected = ["command1", "command2", "command3"]
    assert result == expected

    calls = [
        call.filter(patient__id="patientUuid", note__id="noteUuid", state="staged"),
        call.filter().order_by("dbid"),
    ]
    assert command_db.mock_calls == calls
    reset_mocks()


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

    tested = LimitedCacheLoader
    with patch.object(Constants, "MAX_CHARGE_DESCRIPTIONS", 99):
        # too many records
        charge_description_db.count.side_effect = [100]
        charge_description_db.all.return_value.order_by.side_effect = []
        result = tested.charge_descriptions()
        assert result == []
        calls = [call.count()]
        assert charge_description_db.mock_calls == calls
        reset_mocks()

        # not too many records
        charge_description_db.count.side_effect = [99]
        charge_description_db.all.return_value.order_by.side_effect = [charge_descriptions]
        result = tested.charge_descriptions()
        expected = [
            ChargeDescription(full_name="theFullNameD", short_name="theShortNameA", cpt_code="code754"),
            ChargeDescription(full_name="theFullNameF", short_name="theShortNameB", cpt_code="code565"),
            ChargeDescription(full_name="theFullNameG", short_name="theShortNameD", cpt_code="code486"),
            ChargeDescription(full_name="theFullNameC", short_name="theShortNameC", cpt_code="code752"),
        ]
        assert result == expected
        calls = [call.count(), call.all(), call.all().order_by("cpt_code")]
        assert charge_description_db.mock_calls == calls
        reset_mocks()


@patch.object(Condition, "codings")
@patch.object(Condition, "objects")
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
            Condition(id=uuid5(NAMESPACE_DNS, "2"), clinical_status="resolved", surgical=False),
            Condition(id=uuid5(NAMESPACE_DNS, "3"), clinical_status="resolved", surgical=True),
            Condition(id=uuid5(NAMESPACE_DNS, "4"), clinical_status="resolved", surgical=False),
            Condition(id=uuid5(NAMESPACE_DNS, "5"), clinical_status="active"),
            Condition(id=uuid5(NAMESPACE_DNS, "6"), clinical_status="resolved"),
            Condition(id=uuid5(NAMESPACE_DNS, "7"), clinical_status="active"),
        ],
    ]
    tested = helper_instance()
    result = tested.retrieve_conditions()

    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1a", code="CODE12.3"),
        CodedItem(uuid="c8691da2-158a-5ed6-8537-0e6f140801f2", label="display5a", code="CODE88.88"),
    ]
    assert result[0] == expected
    expected = [
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display4a", code="CODE45"),
        CodedItem(uuid="6ed955c6-506a-5343-9be4-2c0afae02eef", label="display3a", code="CODE98.76"),
    ]
    assert result[1] == expected
    expected = [CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display2c", code="44")]
    assert result[2] == expected

    calls = [
        call.committed(),
        call.committed().for_patient("patientUuid"),
        call.committed().for_patient().filter(clinical_status__in=["active", "resolved"]),
        call.committed().for_patient().filter().order_by("-dbid"),
    ]
    assert condition_db.mock_calls == calls

    calls = [
        call.filter(system__in=[CodeSystems.ICD10, CodeSystems.SNOMED]),
        call.filter().annotate(
            system_order=Case(
                When(system=CodeSystems.ICD10, then=Value(1)),
                When(system=CodeSystems.SNOMED, then=Value(2)),
            ),
        ),
        call.filter().annotate().order_by("system_order"),
        call.filter().annotate().order_by().first(),
    ]
    assert codings_db.mock_calls == calls * 7
    reset_mocks()


@patch.object(Goal, "objects")
def test_current_goals(goal_db):
    def reset_mocks():
        goal_db.reset_mock()

    goal_db.filter.return_value.order_by.side_effect = [
        [
            Goal(id=uuid5(NAMESPACE_DNS, "1"), dbid=258, goal_statement="statement1"),
            Goal(id=uuid5(NAMESPACE_DNS, "2"), dbid=259, goal_statement="statement2"),
            Goal(id=uuid5(NAMESPACE_DNS, "3"), dbid=267, goal_statement="statement3"),
        ],
    ]
    tested = helper_instance()
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", code="258", label="statement1"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", code="259", label="statement2"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", code="267", label="statement3"),
    ]

    result = tested.current_goals()
    assert result == expected
    calls = [
        call.filter(
            patient__id="patientUuid",
            lifecycle_status__in=[
                GoalLifecycleStatus.PROPOSED,
                GoalLifecycleStatus.PLANNED,
                GoalLifecycleStatus.ACCEPTED,
                GoalLifecycleStatus.ACTIVE,
                GoalLifecycleStatus.ON_HOLD,
            ],
            committer_id__isnull=False,
            entered_in_error_id__isnull=True,
        ),
        call.filter().order_by("-dbid"),
    ]
    assert goal_db.mock_calls == calls
    reset_mocks()


@patch.object(Medication, "codings")
@patch.object(Medication, "objects")
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
        [MedicationCoding(system=fdb, display="display4c", code="CODE5654")],
    ]
    medication_db.committed.return_value.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Medication(id=uuid5(NAMESPACE_DNS, "1"), national_drug_code="ndc1", potency_unit_code="puc1"),
            Medication(id=uuid5(NAMESPACE_DNS, "2"), national_drug_code="ndc2", potency_unit_code="puc2"),
            Medication(id=uuid5(NAMESPACE_DNS, "3"), national_drug_code="ndc3", potency_unit_code="puc3"),
            Medication(id=uuid5(NAMESPACE_DNS, "4"), national_drug_code="ndc4", potency_unit_code="puc4"),
        ],
    ]

    tested = helper_instance()
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
    calls = [
        call.committed(),
        call.committed().for_patient("patientUuid"),
        call.committed().for_patient().filter(status="active"),
        call.committed().for_patient().filter().order_by("-dbid"),
    ]
    assert medication_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()


def test_immunization_from():
    tested = LimitedCacheLoader

    tests = [
        (
            [
                ImmunizationStatementCoding(
                    system="http://hl7.org/fhir/sid/cvx",
                    display="theDisplayCvx",
                    code="theCVX",
                ),
                ImmunizationStatementCoding(
                    system="http://www.ama-assn.org/go/cpt",
                    display="theDisplayCpt",
                    code="theCPT",
                ),
            ],
            ImmunizationCached(
                uuid="theRecordUuid",
                label="theDisplayCpt",
                code_cvx="theCVX",
                code_cpt="theCPT",
                comments="theComments",
                approximate_date=date(2025, 9, 21),
            ),
        ),
        (
            [
                ImmunizationCoding(
                    system="http://www.ama-assn.org/go/cpt",
                    display="theDisplayCpt",
                    code="theCPT",
                ),
                ImmunizationCoding(
                    system="http://hl7.org/fhir/sid/cvx",
                    display="theDisplayCvx",
                    code="theCVX",
                ),
            ],
            ImmunizationCached(
                uuid="theRecordUuid",
                label="theDisplayCvx",
                code_cvx="theCVX",
                code_cpt="theCPT",
                comments="theComments",
                approximate_date=date(2025, 9, 21),
            ),
        ),
    ]

    for coding_records, expected in tests:
        result = tested.immunization_from(
            "theRecordUuid",
            "theComments",
            date(2025, 9, 21),
            coding_records,
        )
        assert result == expected


@patch.object(LimitedCacheLoader, "immunization_from")
@patch.object(ImmunizationStatement, "coding")
@patch.object(ImmunizationStatement, "objects")
@patch.object(Immunization, "codings")
@patch.object(Immunization, "objects")
def test_current_immunizations(
    immunization_db,
    immunization_codings_db,
    immunization_statement_db,
    immunization_statement_coding_db,
    immunization_from,
):
    def reset_mocks():
        immunization_db.reset_mock()
        immunization_codings_db.reset_mock()
        immunization_statement_db.reset_mock()
        immunization_statement_coding_db.reset_mock()
        immunization_from.reset_mock()

    date_times = [
        datetime(2025, 9, 21, 8, 53, 21, 123456, tzinfo=timezone.utc),
        datetime(2025, 9, 22, 8, 53, 22, 123456, tzinfo=timezone.utc),
        datetime(2025, 9, 23, 8, 53, 23, 123456, tzinfo=timezone.utc),
    ]

    dates = [
        date(2025, 9, 24),
        date(2025, 9, 25),
        date(2025, 9, 26),
    ]

    immunization_codings_db.all.side_effect = [
        "theImmunizationCodings0",
        "theImmunizationCodings1",
        "theImmunizationCodings2",
    ]
    immunization_statement_coding_db.all.side_effect = [
        "theImmunizationStatementCoding0",
        "theImmunizationStatementCoding1",
        "theImmunizationStatementCoding2",
    ]
    immunization_db.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            Immunization(
                id=uuid5(NAMESPACE_DNS, "1"),
                sig_original="theSigOriginal1",
                note=Note(datetime_of_service=date_times[0]),
            ),
            Immunization(
                id=uuid5(NAMESPACE_DNS, "2"),
                sig_original="theSigOriginal2",
                note=Note(datetime_of_service=date_times[1]),
            ),
            Immunization(
                id=uuid5(NAMESPACE_DNS, "3"),
                sig_original="theSigOriginal3",
                note=Note(datetime_of_service=date_times[2]),
            ),
        ],
    ]
    immunization_statement_db.for_patient.return_value.filter.return_value.order_by.side_effect = [
        [
            ImmunizationStatement(
                id=uuid5(NAMESPACE_DNS, "1"),
                comment="theComment1",
                date=dates[0],
            ),
            ImmunizationStatement(
                id=uuid5(NAMESPACE_DNS, "2"),
                comment="theComment2",
                date=dates[1],
            ),
            ImmunizationStatement(
                id=uuid5(NAMESPACE_DNS, "3"),
                comment="theComment3",
                date=dates[2],
            ),
        ],
    ]
    immunization_from.side_effect = [f"theImmunization{i}" for i in range(6)]
    expected = [
        "theImmunization0",
        "theImmunization1",
        "theImmunization2",
        "theImmunization3",
        "theImmunization4",
        "theImmunization5",
    ]

    tested = helper_instance()

    result = tested.current_immunizations()
    assert result == expected
    calls = [
        call.for_patient("patientUuid"),
        call.for_patient().filter(deleted=False),
        call.for_patient().filter().order_by("-dbid"),
    ]
    assert immunization_db.mock_calls == calls
    assert immunization_statement_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all()]
    assert immunization_codings_db.mock_calls == calls
    assert immunization_statement_coding_db.mock_calls == calls
    calls = [
        call(
            "b04965e6-a9bb-591f-8f8a-1adcb2c8dc39",
            "theSigOriginal1",
            date(2025, 9, 21),
            "theImmunizationCodings0",
        ),
        call(
            "4b166dbe-d99d-5091-abdd-95b83330ed3a",
            "theSigOriginal2",
            date(2025, 9, 22),
            "theImmunizationCodings1",
        ),
        call(
            "98123fde-012f-5ff3-8b50-881449dac91a",
            "theSigOriginal3",
            date(2025, 9, 23),
            "theImmunizationCodings2",
        ),
        call(
            "b04965e6-a9bb-591f-8f8a-1adcb2c8dc39",
            "theComment1",
            date(2025, 9, 24),
            "theImmunizationStatementCoding0",
        ),
        call(
            "4b166dbe-d99d-5091-abdd-95b83330ed3a",
            "theComment2",
            date(2025, 9, 25),
            "theImmunizationStatementCoding1",
        ),
        call(
            "98123fde-012f-5ff3-8b50-881449dac91a",
            "theComment3",
            date(2025, 9, 26),
            "theImmunizationStatementCoding2",
        ),
    ]
    assert immunization_from.mock_calls == calls
    reset_mocks()


@patch.object(AllergyIntolerance, "codings")
@patch.object(AllergyIntolerance, "objects")
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
    calls = [
        call.committed(),
        call.committed().for_patient("patientUuid"),
        call.committed().for_patient().filter(status="active"),
        call.committed().for_patient().filter().order_by("-dbid"),
    ]
    assert allergy_db.mock_calls == calls
    calls = [call.all(), call.all(), call.all()]
    assert codings_db.mock_calls == calls
    reset_mocks()


def test_family_history():
    tested = LimitedCacheLoader
    result = tested.family_history()
    assert result == []


@patch.object(NoteType, "objects")
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
    tested = LimitedCacheLoader
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="noteType1", code="code1"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="noteType2", code="code2"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="noteType3", code="code3"),
    ]
    result = tested.existing_note_types()
    assert result == expected
    calls = [call.filter(is_active=True, is_visible=True, is_scheduleable=True), call.filter().order_by("-dbid")]
    assert note_type_db.mock_calls == calls
    reset_mocks()


@patch.object(ReasonForVisitSettingCoding, "objects")
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
    tested = LimitedCacheLoader
    expected = [
        CodedItem(uuid="b04965e6-a9bb-591f-8f8a-1adcb2c8dc39", label="display1", code="code1"),
        CodedItem(uuid="4b166dbe-d99d-5091-abdd-95b83330ed3a", label="display2", code="code2"),
        CodedItem(uuid="98123fde-012f-5ff3-8b50-881449dac91a", label="display3", code="code3"),
    ]
    result = tested.existing_reason_for_visits()
    assert result == expected
    calls = [call.order_by("-dbid")]
    assert rfv_coding_db.mock_calls == calls
    reset_mocks()


@patch.object(CareTeamRole, "objects")
def test_existing_roles(care_team_role_db):
    def reset_mocks():
        care_team_role_db.reset_mock()

    care_team_role_db.filter.return_value.distinct.side_effect = [
        [
            CareTeamRole(dbid=571, display="display1", code="code1"),
            CareTeamRole(dbid=572, display="display2", code="code2"),
            CareTeamRole(dbid=573, display="display3", code="code3"),
        ],
    ]
    tested = helper_instance()
    expected = [
        CodedItem(uuid="571", label="display1", code=""),
        CodedItem(uuid="572", label="display2", code=""),
        CodedItem(uuid="573", label="display3", code=""),
    ]
    result = tested.existing_roles()
    assert result == expected
    calls = [call.filter(care_teams__patient__id="patientUuid"), call.filter().distinct()]
    assert care_team_role_db.mock_calls == calls
    reset_mocks()


@patch.object(Staff, "top_clinical_role", new_callable=PropertyMock)
@patch.object(Staff, "objects")
def test_existing_staff_members(staff_db, top_clinical_role):
    def reset_mocks():
        staff_db.reset_mock()
        top_clinical_role.reset_mock()

    staff_db.filter.return_value.order_by.side_effect = [
        [
            Staff(dbid=1245, first_name="firstName1", last_name="lastName1"),
            Staff(dbid=1277, first_name="firstName2", last_name="lastName2"),
            Staff(dbid=1296, first_name="firstName3", last_name="lastName3"),
        ],
    ]
    top_clinical_role.side_effect = [
        None,
        StaffRole(domain=StaffRole.RoleDomain("CLI"), role_type=StaffRole.RoleType("NON-LICENSED")),
        StaffRole(domain=StaffRole.RoleDomain("ADM"), role_type=StaffRole.RoleType("PROVIDER")),
    ]

    tested = LimitedCacheLoader
    expected = [
        CodedItem(uuid="1245", label="firstName1 lastName1", code=""),
        CodedItem(uuid="1277", label="firstName2 lastName2 (Clinical/Non-Licensed)", code=""),
        CodedItem(uuid="1296", label="firstName3 lastName3 (Administrative/Provider)", code=""),
    ]
    result = tested.existing_staff_members()
    assert result == expected
    calls = [call.filter(active=True), call.filter().order_by("last_name")]
    assert staff_db.mock_calls == calls
    reset_mocks()


@patch.object(TaskLabel, "objects")
def test_existing_task_labels(task_label_db):
    def reset_mocks():
        task_label_db.reset_mock()

    task_label_db.filter.return_value.order_by.side_effect = [
        [TaskLabel(dbid=1245, name="name1"), TaskLabel(dbid=1277, name="name2"), TaskLabel(dbid=1296, name="name3")],
    ]
    tested = LimitedCacheLoader
    expected = [
        CodedItem(uuid="1245", label="name1", code=""),
        CodedItem(uuid="1277", label="name2", code=""),
        CodedItem(uuid="1296", label="name3", code=""),
    ]
    result = tested.existing_task_labels()
    assert result == expected
    calls = [call.filter(active=True), call.filter().order_by("name")]
    assert task_label_db.mock_calls == calls
    reset_mocks()


@patch.object(Team, "objects")
def test_existing_teams(team_db):
    def reset_mocks():
        team_db.reset_mock()

    team_db.order_by.side_effect = [
        [
            Team(dbid=571, name="name1"),
            Team(dbid=572, name="name2"),
            Team(dbid=573, name="name3"),
        ],
    ]
    tested = LimitedCacheLoader
    expected = [
        CodedItem(uuid="571", label="name1", code=""),
        CodedItem(uuid="572", label="name2", code=""),
        CodedItem(uuid="573", label="name3", code=""),
    ]
    result = tested.existing_teams()
    assert result == expected
    calls = [call.order_by("name")]
    assert team_db.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.limited_cache_loader.date")
@patch.object(Observation, "objects")
def test_demographic__str__(observation_db, mock_date):
    def reset_mocks():
        observation_db.reset_mock()
        mock_date.reset_mock()

    mock_date.today.return_value = date(2025, 2, 5)

    tests = [
        (
            "F",
            date(1941, 2, 7),
            False,
            "the patient is a elderly woman, born on February 07, 1941 (age 83) and weight 124.38 pounds",
        ),
        (
            "F",
            date(1941, 2, 7),
            True,
            "the patient is a elderly woman, born on <DOB REDACTED> (age 83) and weight 124.38 pounds",
        ),
        (
            "F",
            date(2000, 2, 7),
            False,
            "the patient is a woman, born on February 07, 2000 (age 24) and weight 124.38 pounds",
        ),
        (
            "F",
            date(2020, 2, 7),
            False,
            "the patient is a girl, born on February 07, 2020 (age 4) and weight 124.38 pounds",
        ),
        (
            "F",
            date(2024, 7, 2),
            False,
            "the patient is a baby girl, born on July 02, 2024 (age 7 months) and weight 124.38 pounds",
        ),
        (
            "O",
            date(1941, 2, 7),
            False,
            "the patient is a elderly man, born on February 07, 1941 (age 83) and weight 124.38 pounds",
        ),
        (
            "O",
            date(2000, 2, 7),
            False,
            "the patient is a man, born on February 07, 2000 (age 24) and weight 124.38 pounds",
        ),
        (
            "O",
            date(2020, 2, 7),
            False,
            "the patient is a boy, born on February 07, 2020 (age 4) and weight 124.38 pounds",
        ),
        (
            "O",
            date(2024, 7, 2),
            False,
            "the patient is a baby boy, born on July 02, 2024 (age 7 months) and weight 124.38 pounds",
        ),
        (
            "O",
            date(2024, 7, 2),
            True,
            "the patient is a baby boy, born on <DOB REDACTED> (age 7 months) and weight 124.38 pounds",
        ),
    ]

    for sex_at_birth, birth_date, obfuscate, expected in tests:
        patient = factories.PatientFactory(sex_at_birth=sex_at_birth, birth_date=birth_date)
        observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
            Observation(units="oz", value="1990"),
        ]
        tested = helper_instance(patient_uuid=patient.id, obfuscate=obfuscate)

        result = tested.demographic__str__()
        assert result == expected, f" ---> {sex_at_birth} - {birth_date}"
        calls = [
            call.for_patient(patient.id),
            call.for_patient().filter(name="weight", category="vital-signs"),
            call.for_patient().filter().order_by("-effective_datetime"),
            call.for_patient().filter().order_by().first(),
        ]
        assert observation_db.mock_calls == calls
        calls = [call.today()]
        assert mock_date.mock_calls == calls
        reset_mocks()

    # no weight
    patient = factories.PatientFactory(sex_at_birth="F", birth_date=date(2000, 2, 7))
    observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [None]
    tested = helper_instance(patient_uuid=patient.id, obfuscate=False)
    result = tested.demographic__str__()
    expected = "the patient is a woman, born on February 07, 2000 (age 24)"
    assert result == expected
    calls = [
        call.for_patient(patient.id),
        call.for_patient().filter(name="weight", category="vital-signs"),
        call.for_patient().filter().order_by("-effective_datetime"),
        call.for_patient().filter().order_by().first(),
    ]
    assert observation_db.mock_calls == calls
    calls = [call.today()]
    assert mock_date.mock_calls == calls
    reset_mocks()

    # weight as pounds
    patient = factories.PatientFactory(sex_at_birth="F", birth_date=date(2000, 2, 7))
    observation_db.for_patient.return_value.filter.return_value.order_by.return_value.first.side_effect = [
        Observation(units="any", value="125"),
    ]
    tested = helper_instance(patient_uuid=patient.id, obfuscate=False)
    result = tested.demographic__str__()
    expected = "the patient is a woman, born on February 07, 2000 (age 24) and weight 125.00 pounds"
    assert result == expected
    calls = [
        call.for_patient(patient.id),
        call.for_patient().filter(name="weight", category="vital-signs"),
        call.for_patient().filter().order_by("-effective_datetime"),
        call.for_patient().filter().order_by().first(),
    ]
    assert observation_db.mock_calls == calls
    calls = [call.today()]
    assert mock_date.mock_calls == calls
    reset_mocks()


@patch.object(PracticeLocation, "settings")
@patch.object(PracticeLocation, "objects")
@patch.object(Staff, "objects")
def test_practice_setting(staff_db, practice_location_db, practice_settings_db):
    def reset_mocks():
        staff_db.reset_mock()
        practice_location_db.reset_mock()
        practice_settings_db.reset_mock()

    tested = helper_instance()

    # all good
    # -- provider has no primary practice
    tested._instance_settings = {}
    staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=None)]
    practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [
        PracticeLocationSetting(value="theValue"),
    ]

    result = tested.practice_setting("theSetting")
    expected = "theValue"
    assert result == expected

    calls = [call.filter(id="providerUuid"), call.filter().first()]
    assert staff_db.mock_calls == calls
    calls = [call.order_by("dbid"), call.order_by().first()]
    assert practice_location_db.mock_calls == calls
    calls = [call.filter(name="theSetting"), call.filter().order_by("dbid"), call.filter().order_by().first()]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()
    # -- provider has one primary practice
    staff_db.filter.return_value.first.side_effect = [
        Staff(primary_practice_location=PracticeLocation(full_name="theLocation")),
    ]
    practice_location_db.order_by.return_value.first.side_effect = []
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [
        PracticeLocationSetting(value="theValue"),
    ]

    result = tested.practice_setting("theSetting")
    expected = "theValue"
    assert result == expected

    calls = [call.filter(id="providerUuid"), call.filter().first()]
    assert staff_db.mock_calls == calls
    assert practice_location_db.mock_calls == []
    calls = [call.filter(name="theSetting"), call.filter().order_by("dbid"), call.filter().order_by().first()]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()

    # no setting found
    tested._instance_settings = {}
    staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=None)]
    practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [None]

    result = tested.practice_setting("theSetting")
    assert result is None

    calls = [call.filter(id="providerUuid"), call.filter().first()]
    assert staff_db.mock_calls == calls
    calls = [call.order_by("dbid"), call.order_by().first()]
    assert practice_location_db.mock_calls == calls
    calls = [call.filter(name="theSetting"), call.filter().order_by("dbid"), call.filter().order_by().first()]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()

    # no practice found
    tested._instance_settings = {}
    staff_db.filter.return_value.first.side_effect = [Staff(primary_practice_location=None)]
    practice_location_db.order_by.return_value.first.side_effect = [None]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = []

    result = tested.practice_setting("theSetting")
    assert result is None

    calls = [call.filter(id="providerUuid"), call.filter().first()]
    assert staff_db.mock_calls == calls
    calls = [call.order_by("dbid"), call.order_by().first()]
    assert practice_location_db.mock_calls == calls
    assert practice_settings_db.mock_calls == []
    reset_mocks()

    # no provider found
    tested._instance_settings = {}
    staff_db.filter.return_value.first.side_effect = [None]
    practice_location_db.order_by.return_value.first.side_effect = [PracticeLocation(full_name="theLocation")]
    practice_settings_db.filter.return_value.order_by.return_value.first.side_effect = [
        PracticeLocationSetting(value="theValue"),
    ]

    result = tested.practice_setting("theSetting")
    expected = "theValue"
    assert result == expected

    calls = [call.filter(id="providerUuid"), call.filter().first()]
    assert staff_db.mock_calls == calls
    calls = [call.order_by("dbid"), call.order_by().first()]
    assert practice_location_db.mock_calls == calls
    calls = [call.filter(name="theSetting"), call.filter().order_by("dbid"), call.filter().order_by().first()]
    assert practice_settings_db.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCacheLoader, "practice_setting")
@patch.object(LabPartner, "objects")
def test_preferred_lab_partner(lab_partner_db, practice_setting):
    def reset_mocks():
        lab_partner_db.reset_mock()
        practice_setting.reset_mock()

    tested = helper_instance()

    tests = [
        (None, CodedItem(uuid="", label="thePreferredLab", code="")),
        (LabPartner(id="uuidLab", name="theLabPartner"), CodedItem(uuid="uuidLab", label="thePreferredLab", code="")),
    ]

    for lab_partner, expected in tests:
        lab_partner_db.filter.return_value.first.side_effect = [lab_partner]
        practice_setting.side_effect = ["thePreferredLab"]

        result = tested.preferred_lab_partner()
        assert result == expected

        calls = [call.filter(name="thePreferredLab"), call.filter().first()]
        assert lab_partner_db.mock_calls == calls
        calls = [call("preferredLabPartner")]
        assert practice_setting.mock_calls == calls
        reset_mocks()


@patch.object(LimitedCacheLoader, "charge_descriptions")
@patch.object(LimitedCacheLoader, "existing_teams")
@patch.object(LimitedCacheLoader, "existing_task_labels")
@patch.object(LimitedCacheLoader, "existing_staff_members")
@patch.object(LimitedCacheLoader, "existing_roles")
@patch.object(LimitedCacheLoader, "existing_reason_for_visits")
@patch.object(LimitedCacheLoader, "preferred_lab_partner")
@patch.object(LimitedCacheLoader, "existing_note_types")
@patch.object(LimitedCacheLoader, "current_medications")
@patch.object(LimitedCacheLoader, "current_immunizations")
@patch.object(LimitedCacheLoader, "current_goals")
@patch.object(LimitedCacheLoader, "family_history")
@patch.object(LimitedCacheLoader, "demographic__str__")
@patch.object(LimitedCacheLoader, "retrieve_conditions")
@patch.object(LimitedCacheLoader, "current_allergies")
@patch.object(LimitedCacheLoader, "practice_setting")
@patch.object(LimitedCacheLoader, "commands_to_coded_items")
@patch.object(LimitedCacheLoader, "current_commands")
def test_load_from_database(
    current_commands,
    commands_to_coded_items,
    practice_setting,
    current_allergies,
    retrieve_conditions,
    demographic,
    family_history,
    current_goals,
    current_immunizations,
    current_medications,
    existing_note_types,
    preferred_lab_partner,
    existing_reason_for_visits,
    existing_roles,
    existing_staff_members,
    existing_task_labels,
    existing_teams,
    charge_descriptions,
):
    def reset_mocks():
        current_commands.reset_mock()
        commands_to_coded_items.reset_mock()
        practice_setting.reset_mock()
        current_allergies.reset_mock()
        retrieve_conditions.reset_mock()
        demographic.reset_mock()
        family_history.reset_mock()
        current_goals.reset_mock()
        current_immunizations.reset_mock()
        current_medications.reset_mock()
        existing_note_types.reset_mock()
        preferred_lab_partner.reset_mock()
        existing_reason_for_visits.reset_mock()
        existing_roles.reset_mock()
        existing_staff_members.reset_mock()
        existing_task_labels.reset_mock()
        existing_teams.reset_mock()
        charge_descriptions.reset_mock()

    for obfuscate in [True, False]:
        tested = helper_instance(obfuscate=obfuscate)

        current_commands.side_effect = ["theCurrentCommands"]
        commands_to_coded_items.side_effect = ["theCommandsToCodedItems"]
        practice_setting.side_effect = ["thePracticeSetting1", "thePracticeSetting2"]
        current_allergies.side_effect = ["theCurrentAllergies"]
        retrieve_conditions.side_effect = [("theConditions", "theConditionHistory", "theSurgeryHistory")]
        demographic.side_effect = ["theDemographic"]
        family_history.side_effect = ["theFamilyHistory"]
        current_goals.side_effect = ["theCurrentGoals"]
        current_immunizations.side_effect = ["theCurrentImmunizations"]
        current_medications.side_effect = ["theCurrentMedications"]
        existing_note_types.side_effect = ["theExistingNoteTypes"]
        preferred_lab_partner.side_effect = ["thePreferredLabPartner"]
        existing_reason_for_visits.side_effect = ["theExistingReasonForVisits"]
        existing_roles.side_effect = ["theExistingRoles"]
        existing_staff_members.side_effect = ["theExistingStaffMembers"]
        existing_task_labels.side_effect = ["theExistingTaskLabels"]
        existing_teams.side_effect = ["theExistingTeams"]
        charge_descriptions.side_effect = ["theChargeDescriptions"]

        result = tested.load_from_database()
        assert isinstance(result, LimitedCache)
        assert result._actual_staged_commands == "theCurrentCommands"
        assert result._coded_staged_commands == "theCommandsToCodedItems"
        assert result._instance_settings == {
            "preferredLabPartner": "thePracticeSetting1",
            "serviceAreaZipCodes": "thePracticeSetting2",
        }
        assert result._allergies == "theCurrentAllergies"
        assert result._conditions == "theConditions"
        assert result._condition_history == "theConditionHistory"
        assert result._surgery_history == "theSurgeryHistory"
        assert result._demographic == "theDemographic"
        assert result._family_history == "theFamilyHistory"
        assert result._goals == "theCurrentGoals"
        assert result._immunizations == "theCurrentImmunizations"
        assert result._medications == "theCurrentMedications"
        assert result._note_type == "theExistingNoteTypes"
        assert result._preferred_lab_partner == "thePreferredLabPartner"
        assert result._reason_for_visit == "theExistingReasonForVisits"
        assert result._roles == "theExistingRoles"
        assert result._staff_members == "theExistingStaffMembers"
        assert result._task_labels == "theExistingTaskLabels"
        assert result._teams == "theExistingTeams"
        assert result._charge_descriptions == "theChargeDescriptions"
        assert result._lab_tests == {}
        assert result._local_data == False

        calls = [call("theCurrentCommands", tested.commands_policy, not obfuscate)]
        assert commands_to_coded_items.mock_calls == calls
        calls = [
            call("preferredLabPartner"),
            call("serviceAreaZipCodes"),
        ]
        assert practice_setting.mock_calls == calls
        calls = [call()]
        assert current_commands.mock_calls == calls
        assert current_allergies.mock_calls == calls
        assert retrieve_conditions.mock_calls == calls
        assert demographic.mock_calls == calls
        assert family_history.mock_calls == calls
        assert current_goals.mock_calls == calls
        assert current_immunizations.mock_calls == calls
        assert current_medications.mock_calls == calls
        assert existing_note_types.mock_calls == calls
        assert preferred_lab_partner.mock_calls == calls
        assert existing_reason_for_visits.mock_calls == calls
        assert existing_roles.mock_calls == calls
        assert existing_staff_members.mock_calls == calls
        assert existing_task_labels.mock_calls == calls
        assert existing_teams.mock_calls == calls
        assert charge_descriptions.mock_calls == calls
        reset_mocks()


def test_load_from_json():
    cache = {
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
        "currentImmunization": [
            {
                "uuid": "uuid321",
                "label": "label321",
                "codeCpt": "codeCpt321",
                "codeCvx": "codeCvx321",
                "comments": "theComments321",
                "approximateDate": "2025-07-21",
            },
            {
                "uuid": "uuid323",
                "label": "label323",
                "codeCpt": "codeCpt323",
                "codeCvx": "codeCvx323",
                "comments": "theComments323",
                "approximateDate": "2025-07-23",
            },
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
        "existingRoles": [
            {"code": "code431", "label": "label431", "uuid": "uuid431"},
            {"code": "code473", "label": "label473", "uuid": "uuid473"},
        ],
        "existingStaffMembers": [
            {"code": "code037", "label": "label037", "uuid": "uuid037"},
            {"code": "code137", "label": "label137", "uuid": "uuid137"},
        ],
        "existingTeams": [
            {"code": "code894", "label": "label894", "uuid": "uuid894"},
            {"code": "code873", "label": "label873", "uuid": "uuid873"},
        ],
        "existingTaskLabels": [
            {"code": "code091", "label": "label091", "uuid": "uuid091"},
            {"code": "code191", "label": "label191", "uuid": "uuid191"},
        ],
        "familyHistory": [
            {"code": "code010", "label": "label010", "uuid": "uuid010"},
            {"code": "code110", "label": "label110", "uuid": "uuid110"},
        ],
        "stagedCommands": {
            "keyX": [{"code": "code1", "label": "label1", "uuid": "uuid1"}],
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
        "preferredLabPartner": {"uuid": "theUuid", "label": "theLabel", "code": "theCode"},
        "labTests": {"word1 word2": [{"code": "code157", "label": "label157", "uuid": "uuid157"}]},
    }
    tested = LimitedCacheLoader

    # without settings
    result = tested.load_from_json(cache)
    assert isinstance(result, LimitedCache)

    assert result._coded_staged_commands == {
        "keyX": [CodedItem(code="code1", label="label1", uuid="xyz0000")],
        "keyY": [],
        "keyZ": [
            CodedItem(code="code3", label="label3", uuid="xyz2000"),
            CodedItem(code="code2", label="label2", uuid="xyz2001"),
        ],
    }
    assert result.demographic__str__() == "theDemographic"

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
    assert result.current_immunizations() == [
        ImmunizationCached(
            uuid="uuid321",
            label="label321",
            code_cpt="codeCpt321",
            code_cvx="codeCvx321",
            comments="theComments321",
            approximate_date=date(2025, 7, 21),
        ),
        ImmunizationCached(
            uuid="uuid323",
            label="label323",
            code_cpt="codeCpt323",
            code_cvx="codeCvx323",
            comments="theComments323",
            approximate_date=date(2025, 7, 23),
        ),
    ]
    assert result.current_medications() == [
        MedicationCached(
            uuid="uuid006",
            label="label006",
            code_rx_norm="code006",
            code_fdb="",
            national_drug_code="",
            potency_unit_code="",
        ),
        MedicationCached(
            uuid="uuid106",
            label="label106",
            code_rx_norm="code106",
            code_fdb="",
            national_drug_code="",
            potency_unit_code="",
        ),
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
    assert result.existing_roles() == [
        CodedItem(uuid="uuid431", label="label431", code="code431"),
        CodedItem(uuid="uuid473", label="label473", code="code473"),
    ]
    assert result.existing_staff_members() == [
        CodedItem(uuid="uuid037", label="label037", code="code037"),
        CodedItem(uuid="uuid137", label="label137", code="code137"),
    ]
    assert result.existing_teams() == [
        CodedItem(uuid="uuid894", label="label894", code="code894"),
        CodedItem(uuid="uuid873", label="label873", code="code873"),
    ]
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
    assert result.practice_setting("preferredLabPartner") == ""
    assert result.practice_setting("serviceAreaZipCodes") == []
    assert result.preferred_lab_partner() == CodedItem(uuid="theUuid", label="theLabel", code="theCode")

    assert result._lab_tests == {}
    assert result._local_data is True

    # with the settings
    result = tested.load_from_json(
        cache
        | {
            "settings": {
                "preferredLabPartner": "thePreferredLabPartner",
                "serviceAreaZipCodes": ["theServiceAreaZipCodes"],
            }
        }
    )
    assert result.practice_setting("preferredLabPartner") == "thePreferredLabPartner"
    assert result.practice_setting("serviceAreaZipCodes") == ["theServiceAreaZipCodes"]
