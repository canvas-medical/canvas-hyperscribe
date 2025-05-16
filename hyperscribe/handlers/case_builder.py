import json
import re
from typing import Type

from canvas_sdk.commands import (
    VitalsCommand, QuestionnaireCommand, UpdateGoalCommand, ResolveConditionCommand, MedicationStatementCommand, PastSurgicalHistoryCommand,
    PlanCommand, ReasonForVisitCommand, ReferCommand, UpdateDiagnosisCommand, TaskCommand, StructuredAssessmentCommand, StopMedicationCommand,
    ReviewOfSystemsCommand, RemoveAllergyCommand, RefillCommand, PrescribeCommand, PerformCommand, MedicalHistoryCommand, LabOrderCommand,
    InstructCommand, ImagingOrderCommand, HistoryOfPresentIllnessCommand, GoalCommand, FollowUpCommand, FamilyHistoryCommand, PhysicalExamCommand,
    DiagnoseCommand, AdjustPrescriptionCommand, CloseGoalCommand, AssessCommand, AllergyCommand
)
from canvas_sdk.commands.base import _BaseCommand as BaseCommand
from canvas_sdk.commands.commands.questionnaire.question import (ResponseOption)
from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPIRoute
from canvas_sdk.v1.data import Command, Questionnaire

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants


class CaseBuilder(SimpleAPIRoute):
    PATH = "/case_builder"
    CLASS_COMMANDS = [
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
    ]
    CLASS_QUESTIONNAIRES = {
        PhysicalExamCommand: Constants.SCHEMA_KEY_PHYSICAL_EXAM,
        QuestionnaireCommand: Constants.SCHEMA_KEY_QUESTIONNAIRE,
        ReviewOfSystemsCommand: Constants.SCHEMA_KEY_REVIEW_OF_SYSTEM,
        StructuredAssessmentCommand: Constants.SCHEMA_KEY_STRUCTURED_ASSESSMENT,
    }

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    def post(self) -> list[Response | Effect]:
        result: list[Effect] = []
        commands = self.request.json()

        for data in commands:
            class_name = data["class"]
            attributes = data["attributes"]

            for command_class in self.CLASS_COMMANDS:
                if command_class.__name__ == class_name:
                    if command_class in self.CLASS_QUESTIONNAIRES:
                        if effect := self.questionnaire_command_from(command_class, attributes):
                            result.append(effect)
                        continue
                    result.append(self.common_command_from(command_class, attributes))

        return result

    @classmethod
    def command_type(cls, command_class: Type[BaseCommand], prefix: str) -> str:
        command_name = re.sub(r"(?<!^)(?=[A-Z])", "_", command_class.Meta.key)
        return f"{prefix}_{command_name}_COMMAND".upper()

    @classmethod
    def common_command_from(cls, command_class: Type[BaseCommand], attributes: dict) -> Effect:
        command_uuid = attributes.get("command_uuid")
        note_uuid = attributes["note_uuid"]
        payload = {
            "command": command_uuid,
            "data": {
                key: value
                for key, value in attributes.items()
                if key not in ("command_uuid", "note_uuid")
            },
        }
        prefix = "EDIT"
        if command_uuid is None:
            prefix = "ORIGINATE"
            payload["note"] = note_uuid
            payload["line_number"] = -1

        return Effect(
            type=cls.command_type(command_class, prefix),
            payload=json.dumps(payload),
        )

    @classmethod
    def questionnaire_command_from(cls, command_class: Type[QuestionnaireCommand], attributes: dict) -> Effect | None:
        questions = attributes["questions"]
        command_db = Command.objects.filter(
            id=attributes["command_uuid"],
            state="staged",
        ).order_by("dbid").first()

        if command_db and command_db.schema_key in cls.CLASS_QUESTIONNAIRES.values():
            questionnaire_id = command_db.data["questionnaire"]["value"]
            questionnaire = Questionnaire.objects.get(dbid=questionnaire_id)
            result = command_class(
                questionnaire_id=str(questionnaire.id),
                note_uuid=attributes["note_uuid"],
                command_uuid=attributes["command_uuid"],
            )
            for idx, question in enumerate(result.questions):
                if question.type == ResponseOption.TYPE_INTEGER:
                    question.add_response(integer=questions[question.name])
                elif question.type == ResponseOption.TYPE_CHECKBOX:
                    for num, option in enumerate(question.options):
                        choice = questions[question.name][num]
                        question.add_response(option=option, selected=choice["selected"], comment=choice["comment"])
                elif question.type == ResponseOption.TYPE_RADIO:
                    for option in question.options:
                        if option.dbid == questions[question.name]:
                            question.add_response(option=option)
                else:  # question.type == ResponseOption.TYPE_TEXT:
                    question.add_response(text=questions[question.name])

            return result.edit()
        return None
