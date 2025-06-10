from __future__ import annotations

from datetime import date
from re import match
from typing import Iterable

from canvas_sdk.commands.constants import CodeSystems
from canvas_sdk.v1.data import (
    AllergyIntolerance, Condition, Questionnaire, Command,
    Patient, Observation, NoteType, Medication, ReasonForVisitSettingCoding)
from canvas_sdk.v1.data.condition import ClinicalStatus
from canvas_sdk.v1.data.medication import Status
from canvas_sdk.v1.data.patient import SexAtBirth
from django.db.models.expressions import When, Value, Case

from hyperscribe_tuning.handlers.constants import Constants
from hyperscribe_tuning.handlers.implemented_commands import ImplementedCommands
from hyperscribe_tuning.structures.coded_item import CodedItem


class LimitedCache:
    @classmethod
    def icd10_add_dot(cls, code: str) -> str:
        if result := match(r"([A-Za-z]+\d{2})(\d+)", code):
            return f"{result.group(1)}.{result.group(2)}"
        return code

    @classmethod
    def existing_commands_to_coded_items(cls, current_commands: Iterable[Command]) -> dict[str, list[CodedItem]]:
        result: dict[str, list[CodedItem]] = {}
        for command in current_commands:
            for command_class in ImplementedCommands.command_list():
                if command_class.schema_key() == command.schema_key:
                    if coded_item := command_class.staged_command_extract(command.data):
                        key = command.schema_key
                        if key not in result:
                            result[key] = []
                        result[key].append(coded_item)
                    break
        return result

    def __init__(self, patient_uuid: str, staged_commands_to_coded_items: dict[str, list[CodedItem]]):
        self.patient_uuid = patient_uuid
        self._allergies: list[CodedItem] | None = None
        self._condition_history: list[CodedItem] | None = None
        self._conditions: list[CodedItem] | None = None
        self._demographic: str | None = None
        self._family_history: list[CodedItem] | None = None
        self._goals: list[CodedItem] | None = None
        self._medications: list[CodedItem] | None = None
        self._note_type: list[CodedItem] | None = None
        self._questionnaires: list[CodedItem] | None = None
        self._reason_for_visit: list[CodedItem] | None = None
        self._surgery_history: list[CodedItem] | None = None
        self._staged_commands: dict[str, list[CodedItem]] = staged_commands_to_coded_items

    def retrieve_conditions(self) -> None:
        self._conditions = []
        self._condition_history = []
        self._surgery_history = []
        statuses = [ClinicalStatus.ACTIVE, ClinicalStatus.RESOLVED]
        systems = [CodeSystems.ICD10, CodeSystems.SNOMED]
        conditions = Condition.objects.committed().for_patient(self.patient_uuid).filter(clinical_status__in=statuses)
        for condition in conditions.order_by('-dbid'):
            case = Case(When(system=CodeSystems.ICD10, then=Value(1)), When(system=CodeSystems.SNOMED, then=Value(2)))
            coding = condition.codings.filter(system__in=systems).annotate(system_order=case).order_by("system_order").first()

            if coding:
                item = CodedItem(
                    uuid=str(condition.id),
                    label=coding.display,
                    code=self.icd10_add_dot(coding.code),
                )
                if condition.clinical_status == ClinicalStatus.ACTIVE:
                    self._conditions.append(item)
                elif condition.clinical_status == ClinicalStatus.RESOLVED and coding.system == CodeSystems.ICD10:
                    # TODO ^ should be: elif condition.clinical_status == ClinicalStatus.RESOLVED and condition.surgical == False:
                    self._condition_history.append(item)
                elif condition.clinical_status == ClinicalStatus.RESOLVED and coding.system == CodeSystems.SNOMED:
                    # TODO ^ should be: elif condition.clinical_status == ClinicalStatus.RESOLVED and condition.surgical == True:
                    self._surgery_history.append(item)

    def staged_commands_of(self, schema_keys: list[str]) -> list[CodedItem]:
        return [
            command
            for key, commands in self._staged_commands.items() if key in schema_keys
            for command in commands
        ]

    def current_goals(self) -> list[CodedItem]:
        if self._goals is None:
            self._goals = []
            # ATTENTION below code should not be used since there is no way to know if a goal is already closed
            commands = Command.objects.filter(patient__id=self.patient_uuid, schema_key="goal").order_by('-dbid')
            for command in commands:
                self._goals.append(CodedItem(
                    uuid=str(command.id),
                    label=command.data["goal_statement"],
                    code=str(command.dbid),  # TODO should be "", waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
                ))
        return self._goals

    def current_conditions(self) -> list[CodedItem]:
        if self._conditions is None:
            self.retrieve_conditions()
        return self._conditions or []

    def current_medications(self) -> list[CodedItem]:
        if self._medications is None:
            self._medications = []
            medications = Medication.objects.committed().for_patient(self.patient_uuid).filter(status=Status.ACTIVE)
            for medication in medications.order_by('-dbid'):
                for coding in medication.codings.all():
                    if coding.system == CodeSystems.RXNORM:
                        self._medications.append(CodedItem(
                            uuid=str(medication.id),
                            label=coding.display,
                            code=coding.code,
                        ))
        return self._medications

    def current_allergies(self) -> list[CodedItem]:
        if self._allergies is None:
            self._allergies = []
            allergies = AllergyIntolerance.objects.committed().for_patient(self.patient_uuid).filter(status=Status.ACTIVE)
            for allergy in allergies.order_by('-dbid'):
                for coding in allergy.codings.all():
                    if coding.system == CodeSystems.FDB:
                        self._allergies.append(CodedItem(
                            uuid=str(allergy.id),
                            label=coding.display,
                            code=coding.code,
                        ))
        return self._allergies

    def family_history(self) -> list[CodedItem]:
        if self._family_history is None:
            self._family_history = []
        return self._family_history

    def condition_history(self) -> list[CodedItem]:
        if self._condition_history is None:
            self.retrieve_conditions()
        return self._condition_history or []

    def surgery_history(self) -> list[CodedItem]:
        if self._surgery_history is None:
            self.retrieve_conditions()
        return self._surgery_history or []

    def existing_questionnaires(self) -> list[CodedItem]:
        if self._questionnaires is None:
            self._questionnaires = []
            questionnaires = Questionnaire.objects.filter(
                status="AC",
                can_originate_in_charting=True,
                use_case_in_charting="QUES",
            ).order_by('-dbid')
            for questionnaire in questionnaires:
                self._questionnaires.append(CodedItem(
                    uuid=str(questionnaire.id),
                    label=questionnaire.name,
                    code="",
                ))
        return self._questionnaires

    def existing_note_types(self) -> list[CodedItem]:
        if self._note_type is None:
            self._note_type = []
            note_types = NoteType.objects.filter(is_active=True, is_visible=True, is_scheduleable=True).order_by('-dbid')
            for note_type in note_types:
                self._note_type.append(CodedItem(
                    uuid=str(note_type.id),
                    label=note_type.name,
                    code=note_type.code,
                ))
        return self._note_type

    def existing_reason_for_visits(self) -> list[CodedItem]:
        if self._reason_for_visit is None:
            self._reason_for_visit = []
            for rfv in ReasonForVisitSettingCoding.objects.order_by('-dbid'):
                self._reason_for_visit.append(CodedItem(
                    uuid=str(rfv.id),
                    label=rfv.display,
                    code=rfv.code,
                ))
        return self._reason_for_visit

    def demographic__str__(self) -> str:
        if self._demographic is None:
            patient = Patient.objects.get(id=self.patient_uuid)

            is_female = bool(patient.sex_at_birth == SexAtBirth.FEMALE)
            # dob = patient.birth_date.strftime("%B %d, %Y")
            dob = "<DOB REDACTED>"  # principal of minimum disclosure
            today = date.today()
            age = today.year - patient.birth_date.year - ((today.month, today.day) < (patient.birth_date.month, patient.birth_date.day))
            age_str = str(age)
            if age < 2:
                age_str = f"{(today.year - patient.birth_date.year) * 12 + today.month - patient.birth_date.month} months"
                sex_at_birth = "baby girl" if is_female else "baby boy"
            elif age < 20:
                sex_at_birth = "girl" if is_female else "boy"
            elif age > 65:
                sex_at_birth = "elderly woman" if is_female else "elderly man"
            else:
                sex_at_birth = "woman" if is_female else "man"

            self._demographic = f"the patient is a {sex_at_birth}, born on {dob} (age {age_str})"

            weight = Observation.objects.for_patient(
                self.patient_uuid).filter(
                name="weight", category="vital-signs").order_by(
                "-effective_datetime").first()
            if weight and weight.value:
                ratio = 1 / 1
                if weight.units == "oz":
                    ratio = 1 / 16
                weight_str = f"{int(weight.value) * ratio:1.2f} pounds"

                self._demographic = f"{self._demographic} and weight {weight_str}"

        return self._demographic

    def to_json(self) -> dict:
        return {
            "stagedCommands": {
                key: [i._asdict() for i in commands]
                for key, commands in self._staged_commands.items()
            },
            "demographicStr": self.demographic__str__(),
            #
            "conditionHistory": [i._asdict() for i in self.condition_history()],
            "currentAllergies": [i._asdict() for i in self.current_allergies()],
            "currentConditions": [i._asdict() for i in self.current_conditions()],
            "currentGoals": [i._asdict() for i in self.current_goals()],
            "currentMedications": [i._asdict() for i in self.current_medications()],
            "existingQuestionnaires": [i._asdict() for i in self.existing_questionnaires()],
            "existingNoteTypes": [i._asdict() for i in self.existing_note_types()],
            "existingReasonForVisit": [i._asdict() for i in self.existing_reason_for_visits()],
            "familyHistory": [i._asdict() for i in self.family_history()],
            "surgeryHistory": [i._asdict() for i in self.surgery_history()],
        }

    @classmethod
    def load_from_json(cls, cache: dict) -> LimitedCache:
        staged_commands = {
            key: [CodedItem(**i) for i in commands]
            for key, commands in cache.get("stagedCommands", {}).items()
        }

        result = cls(Constants.FAUX_PATIENT_UUID, staged_commands)
        result._demographic = cache.get("demographicStr", "")

        result._condition_history = [CodedItem(**i) for i in cache.get("conditionHistory", [])]
        result._allergies = [CodedItem(**i) for i in cache.get("currentAllergies", [])]
        result._conditions = [CodedItem(**i) for i in cache.get("currentConditions", [])]
        result._goals = [CodedItem(**i) for i in cache.get("currentGoals", [])]
        result._medications = [CodedItem(**i) for i in cache.get("currentMedications", [])]
        result._questionnaires = [CodedItem(**i) for i in cache.get("existingQuestionnaires", [])]
        result._note_type = [CodedItem(**i) for i in cache.get("existingNoteTypes", [])]
        result._reason_for_visit = [CodedItem(**i) for i in cache.get("existingReasonForVisit", [])]
        result._family_history = [CodedItem(**i) for i in cache.get("familyHistory", [])]
        result._surgery_history = [CodedItem(**i) for i in cache.get("surgeryHistory", [])]

        return result
