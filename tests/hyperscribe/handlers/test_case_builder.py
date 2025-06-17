import json
import re
from unittest.mock import patch, call, MagicMock

from canvas_generated.messages.effects_pb2 import Effect
from canvas_generated.messages.events_pb2 import Event as EventRequest
from canvas_sdk.commands import (
    VitalsCommand, QuestionnaireCommand, UpdateGoalCommand, ResolveConditionCommand, MedicationStatementCommand, PastSurgicalHistoryCommand,
    PlanCommand, ReasonForVisitCommand, ReferCommand, UpdateDiagnosisCommand, TaskCommand, StructuredAssessmentCommand, StopMedicationCommand,
    ReviewOfSystemsCommand, RemoveAllergyCommand, RefillCommand, PrescribeCommand, PerformCommand, MedicalHistoryCommand, LabOrderCommand,
    InstructCommand, ImagingOrderCommand, HistoryOfPresentIllnessCommand, GoalCommand, FollowUpCommand, FamilyHistoryCommand, PhysicalExamCommand,
    DiagnoseCommand, AdjustPrescriptionCommand, CloseGoalCommand, AssessCommand, AllergyCommand
)
from canvas_sdk.commands.base import _BaseCommand as BaseCommand
from canvas_sdk.commands.commands.questionnaire import TextQuestion, IntegerQuestion, CheckboxQuestion, RadioQuestion
from canvas_sdk.events import Event
from canvas_sdk.events.base import TargetType
from canvas_sdk.handlers.simple_api import SimpleAPIRoute, Credentials
from canvas_sdk.v1.data import Patient, Questionnaire, Command, ResponseOption

from hyperscribe.handlers.case_builder import CaseBuilder
from hyperscribe.libraries.authenticator import Authenticator
from tests.helper import is_constant


def helper_instance() -> CaseBuilder:
    event = Event(EventRequest(context=json.dumps({
        "method": "POST",
        "path": "/case_builder",
        "query_string": "",
        "body": "",
        "headers": {"Host": "theHost"},
    })))
    event.target = TargetType(id="targetId", type=Patient)
    secrets = {
        "APISigningKey": "theApiSigningKey",
    }
    environment = {}
    instance = CaseBuilder(event, secrets, environment)
    instance._path_pattern = re.compile(r".*")  # TODO this is a hack, find the right way to create the Archiver instance
    return instance


def test_class():
    tested = CaseBuilder
    assert issubclass(tested, SimpleAPIRoute)


def test_constants():
    tested = CaseBuilder
    constants = {
        "PATH": "/case_builder",
        "RESPONDS_TO": ['SIMPLE_API_AUTHENTICATE', 'SIMPLE_API_REQUEST'],  # <--- SimpleAPIBase class
        "CLASS_COMMANDS": [
            AdjustPrescriptionCommand,
            AllergyCommand,
            AssessCommand,
            CloseGoalCommand,
            DiagnoseCommand,
            FamilyHistoryCommand,
            FollowUpCommand,
            GoalCommand,
            HistoryOfPresentIllnessCommand,
            ImagingOrderCommand,
            InstructCommand,
            LabOrderCommand,
            MedicalHistoryCommand,
            MedicationStatementCommand,
            PastSurgicalHistoryCommand,
            PerformCommand,
            PhysicalExamCommand,
            PlanCommand,
            PrescribeCommand,
            QuestionnaireCommand,
            ReasonForVisitCommand,
            ReferCommand,
            RefillCommand,
            RemoveAllergyCommand,
            ResolveConditionCommand,
            ReviewOfSystemsCommand,
            StopMedicationCommand,
            StructuredAssessmentCommand,
            TaskCommand,
            UpdateDiagnosisCommand,
            UpdateGoalCommand,
            VitalsCommand,
        ],
        "CLASS_QUESTIONNAIRES": {
            PhysicalExamCommand: "exam",
            QuestionnaireCommand: "questionnaire",
            ReviewOfSystemsCommand: "ros",
            StructuredAssessmentCommand: "structuredAssessment",
        },
    }
    assert is_constant(tested, constants)


@patch.object(Authenticator, "check")
def test_authenticate(check):
    def reset_mocks():
        check.reset_mock()

    tested = helper_instance()
    tested.request.query_params = {"key": "value"}
    for test in [True, False]:
        check.side_effect = [test]
        result = tested.authenticate(Credentials(tested.request))
        assert result is test
        calls = [call('theApiSigningKey', 1200, {'key': 'value'})]
        assert check.mock_calls == calls
        reset_mocks()


@patch.object(CaseBuilder, "questionnaire_command_from")
@patch.object(CaseBuilder, "common_command_from")
def test_post(common_command_from, questionnaire_command_from):
    def reset_mocks():
        common_command_from.reset_mock()
        questionnaire_command_from.reset_mock()

    tested = helper_instance()

    commands = json.dumps([
        {
            "module": "some.module",
            "class": "TheClass4",
            "attributes": {
                "command_uuid": None,
                "note_uuid": "theNoteUuid",
                "attributeA": "valueA",
                "attributeB": "valueB",
                "attributeC": "valueC",
            },
        },
        {
            "module": "some.module",
            "class": "TheClass4",
            "attributes": {
                "command_uuid": "theCommandUuidX",
                "note_uuid": "theNoteUuid",
                "attributeA": "valueA",
            },
        },
        {
            "module": "some.module",
            "class": "TheClass3",
            "attributes": {
                "command_uuid": "theCommandUuidY",
                "note_uuid": "theNoteUuid",
                "attributeA": "valueA",
                "attributeB": "valueB",
                "attributeC": "valueC",
            },
        },
        {
            "module": "some.module",
            "class": "TheClass3",
            "attributes": {
                "command_uuid": None,
                "note_uuid": "theNoteUuid",
                "attributeA": "valueA",
            },
        },
        {
            "module": "some.module",
            "class": "TheClass5",
            "attributes": {
                "command_uuid": None,
                "note_uuid": "theNoteUuid",
                "attributeA": "valueA",
            },
        },
    ])

    class TheClass1:
        ...

    class TheClass2:
        ...

    class TheClass3:
        ...

    class TheClass4:
        ...

    with patch.object(CaseBuilder, "CLASS_COMMANDS", [TheClass1, TheClass2, TheClass3, TheClass4]):
        with patch.object(CaseBuilder, "CLASS_QUESTIONNAIRES", {TheClass3: "theKey3"}):
            common_command_from.side_effect = [Effect(type="LOG", payload="LogA"), Effect(type="LOG", payload="LogB")]
            questionnaire_command_from.side_effect = [Effect(type="LOG", payload="LogC"), None]

            tested.request.body = commands
            result = tested.post()
            expected = [
                Effect(type="LOG", payload="LogA"),
                Effect(type="LOG", payload="LogB"),
                Effect(type="LOG", payload="LogC"),
            ]
            assert result == expected

            calls = [
                call(TheClass4,
                     {
                         "command_uuid": None,
                         "note_uuid": "theNoteUuid",
                         "attributeA": "valueA",
                         "attributeB": "valueB",
                         "attributeC": "valueC",
                     }),
                call(TheClass4,
                     {
                         "command_uuid": "theCommandUuidX",
                         "note_uuid": "theNoteUuid",
                         "attributeA": "valueA",
                     }),
            ]
            assert common_command_from.mock_calls == calls
            calls = [
                call(TheClass3,
                     {
                         "command_uuid": "theCommandUuidY",
                         "note_uuid": "theNoteUuid",
                         "attributeA": "valueA",
                         "attributeB": "valueB",
                         "attributeC": "valueC",
                     }),
                call(TheClass3,
                     {
                         "command_uuid": None,
                         "note_uuid": "theNoteUuid",
                         "attributeA": "valueA",
                     }),
            ]
            assert questionnaire_command_from.mock_calls == calls
            reset_mocks()


def test_command_type():
    tested = CaseBuilder

    class TheClass(BaseCommand):
        class Meta:
            key = "theClassKey"

    result = tested.command_type(TheClass, "the_prefix")
    expected = "THE_PREFIX_THE_CLASS_KEY_COMMAND"
    assert result == expected


def test_common_command_from():
    tested = CaseBuilder

    # no command uuid
    result = tested.common_command_from(ReasonForVisitCommand, {
        "command_uuid": None,
        "note_uuid": "theNoteUuid",
        "attributeA": "valueA",
        "attributeB": "valueB",
        "attributeC": "valueC",
    })
    expected = Effect(
        type="ORIGINATE_REASON_FOR_VISIT_COMMAND",
        payload=json.dumps({
            "command": None,
            "data": {
                "attributeA": "valueA",
                "attributeB": "valueB",
                "attributeC": "valueC",
            },
            "note": "theNoteUuid",
            "line_number": -1,
        }),
    )
    assert result == expected
    # with command uuid
    result = tested.common_command_from(ReasonForVisitCommand, {
        "command_uuid": "theCommandUuid",
        "note_uuid": "theNoteUuid",
        "attributeA": "valueA",
        "attributeB": "valueB",
        "attributeC": "valueC",
    })
    expected = Effect(
        type="EDIT_REASON_FOR_VISIT_COMMAND",
        payload=json.dumps({
            "command": "theCommandUuid",
            "data": {
                "attributeA": "valueA",
                "attributeB": "valueB",
                "attributeC": "valueC",
            },
        }),
    )
    assert result == expected


@patch.object(Questionnaire, "objects")
@patch.object(Command, "objects")
def test_questionnaire_command_from(command_db, questionnaire_db):
    mock_command = MagicMock()

    def reset_mocks():
        command_db.reset_mock()
        questionnaire_db.reset_mock()
        mock_command.reset_mock()

    tested = CaseBuilder

    questionnaire = Questionnaire(id="questionnaireUuid")
    attributes = {
        "command_uuid": "theCommandUuid",
        "note_uuid": "theNoteUuid",
        "questions": {
            "question-8": 31,
            "question-9": 28,
            "question-10": [
                {
                    "text": "theOption33",
                    "value": 33,
                    "comment": "",
                    "selected": False,
                },
                {
                    "text": "theOption34",
                    "value": 34,
                    "comment": "some comment",
                    "selected": True,
                },
                {
                    "text": "theOption35",
                    "value": 35,
                    "comment": "",
                    "selected": False,
                },
                {
                    "text": "theOption36",
                    "value": 36,
                    "comment": "",
                    "selected": False,
                }
            ],
            "question-11": "the text"
        },
    }
    questions = [
        IntegerQuestion(
            name="question-8",
            label="theTextQuestion",
            coding={},
            options=[],
        ),
        RadioQuestion(
            name="question-9",
            label="theTextQuestion",
            coding={},
            options=[
                ResponseOption(dbid=27),
                ResponseOption(dbid=28),
                ResponseOption(dbid=29),
            ],
        ),
        CheckboxQuestion(
            name="question-10",
            label="theTextQuestion",
            coding={},
            options=[
                ResponseOption(dbid=33),
                ResponseOption(dbid=34),
                ResponseOption(dbid=35),
                ResponseOption(dbid=36),
            ],
        ),
        TextQuestion(
            name="question-11",
            label="theTextQuestion",
            coding={},
            options=[],
        ),
        TextQuestion(
            name="question-17",
            label="otherTextQuestion",
            coding={},
            options=[],
        ),
    ]

    # there is a matching questionnaire
    for schema_key in ["exam", "questionnaire", "ros", "structuredAssessment"]:
        command_db.filter.return_value.order_by.return_value.first.side_effect = [
            Command(schema_key=schema_key, data={"questionnaire": {"value": 117}}),
        ]
        questionnaire_db.get.side_effect = [questionnaire]
        mock_command.return_value.edit.side_effect = ["someEffect"]
        mock_command.return_value.questions = questions

        result = tested.questionnaire_command_from(mock_command, attributes)
        expected = "someEffect"
        assert result == expected

        calls = [
            call.filter(id='theCommandUuid', state='staged'),
            call.filter().order_by('dbid'),
            call.filter().order_by().first(),
        ]
        assert command_db.mock_calls == calls
        calls = [call.get(dbid=117)]
        assert questionnaire_db.mock_calls == calls
        calls = [
            call(questionnaire_id='questionnaireUuid', note_uuid='theNoteUuid', command_uuid='theCommandUuid'),
            call().edit(),
        ]
        assert mock_command.mock_calls == calls
        reset_mocks()

    # there is no matching questionnaire
    command_db.filter.return_value.order_by.return_value.first.side_effect = [
        Command(schema_key="something", data={"questionnaire": {"value": 117}}),
    ]
    questionnaire_db.get.side_effect = [questionnaire]
    mock_command.return_value.edit.side_effect = ["someEffect"]
    mock_command.return_value.questions = questions

    result = tested.questionnaire_command_from(mock_command, attributes)
    assert result is None

    calls = [
        call.filter(id='theCommandUuid', state='staged'),
        call.filter().order_by('dbid'),
        call.filter().order_by().first(),
    ]
    assert command_db.mock_calls == calls
    assert questionnaire_db.mock_calls == []
    assert mock_command.mock_calls == []
    reset_mocks()
