from datetime import date

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.v1.data import Condition, Questionnaire, Command, Patient, Observation
from canvas_sdk.v1.data import Medication
from canvas_sdk.v1.data.allergy_intolerance import AllergyIntolerance
from canvas_sdk.v1.data.condition import ClinicalStatus
from canvas_sdk.v1.data.medication import Status
from canvas_sdk.v1.data.patient import SexAtBirth

from commander.protocols.constants import Constants
from commander.protocols.helper import Helper
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


class Base:

    def __init__(self, settings: Settings, patient_uuid: str, note_uuid: str, provider_uuid: str):
        self.settings = settings
        self.patient_uuid = patient_uuid
        self.note_uuid = note_uuid
        self.provider_uuid = provider_uuid
        self._conditions: list | None = None
        self._allergies: list | None = None
        self._family_history: list | None = None
        self._condition_history: list | None = None
        self._goals: list | None = None
        self._medications: list | None = None
        self._surgery_history: list | None = None
        self._questionnaires: list | None = None
        self._demographic: str | None = None

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    @classmethod
    def schema_key(cls) -> str:
        raise NotImplementedError

    def command_from_json(self, parameters: dict) -> None | _BaseCommand:
        raise NotImplementedError

    def command_parameters(self) -> dict:
        raise NotImplementedError

    def instruction_description(self) -> str:
        raise NotImplementedError

    def instruction_constraints(self) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    def current_goals(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                # CodedItem(
                #     uuid="mmm",
                #     label="Weekend without dermatitis",
                #     code="1523",
                # ),
                # CodedItem(
                #     uuid="nnn",
                #     label="No Fast food dinner",
                #     code="1528",
                # ),
            ]
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
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                # CodedItem(
                #     uuid="ccc",
                #     label="Type 2 diabetes mellitus without complications",
                #     code="E119",
                # ),
                # CodedItem(
                #     uuid="ddd",
                #     label="Essential (primary) hypertension",
                #     code="I10",
                # ),
                # CodedItem(
                #     uuid="eee",
                #     label="Hyperlipidemia, unspecified",
                #     code="E785",
                # ),
            ]
        if self._conditions is None:
            self._conditions = []
            for condition in Condition.objects.committed().for_patient(self.patient_uuid).filter(clinical_status=ClinicalStatus.ACTIVE):
                for coding in condition.codings.all():
                    if coding.system == "ICD-10":
                        self._conditions.append(CodedItem(
                            uuid=str(condition.id),
                            label=coding.display,
                            code=Helper.icd10_add_dot(coding.code),
                        ))
        return self._conditions

    def current_medications(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                # CodedItem(
                #     uuid="967ab04e-3c4d-45d8-849e-56680f609f0b",
                #     label="lisinopril 20 mg tablet",
                #     code="314077",
                # ),
                # CodedItem(
                #     uuid="967ab04e-3c4d-45d8-849e-56680f609f00",
                #     label="hydrochlorothiazide 25 mg tablet",
                #     code="310798",
                # ),
                # CodedItem(
                #     uuid="967ab04e-3c4d-45d8-849e-56680f609f01",
                #     label="Lipitor 10 mg tablet",
                #     code="617312",
                # ),
            ]
        if self._medications is None:
            self._medications = []
            for medication in Medication.objects.committed().for_patient(self.patient_uuid).filter(status=Status.ACTIVE):
                for coding in medication.codings.all():
                    if coding.system == "http://www.nlm.nih.gov/research/umls/rxnorm":
                        self._medications.append(CodedItem(
                            uuid=str(medication.id),
                            label=coding.display,
                            code=coding.code,
                        ))
        return self._medications

    def current_allergies(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                # CodedItem(
                #     uuid="aaa",
                #     label="penicillin G sodium",
                #     code="8228",
                # ),
                # CodedItem(
                #     uuid="bbb",
                #     label="lactose",
                #     code="2432",
                # ),
            ]
        if self._allergies is None:
            self._allergies = []
            for allergy in AllergyIntolerance.objects.committed().for_patient(self.patient_uuid).filter(status=Status.ACTIVE):
                for coding in allergy.codings.all():
                    if coding.system == "http://www.fdbhealth.com/":
                        self._allergies.append(CodedItem(
                            uuid=str(allergy.id),
                            label=coding.display,
                            code=coding.code,
                        ))
        return self._allergies

    def family_history(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return []
        if self._family_history is None:
            self._family_history = []
        return self._family_history

    def condition_history(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return []
        if self._condition_history is None:
            self._condition_history = []
            conditions = Condition.objects.committed().for_patient(self.patient_uuid)
            for condition in conditions.filter(clinical_status=ClinicalStatus.RESOLVED):  # TODO add surgical=False
                for coding in condition.codings.all():
                    if coding.system == "ICD-10":
                        self._condition_history.append(CodedItem(
                            uuid=str(condition.id),
                            label=coding.display,
                            code=Helper.icd10_add_dot(coding.code),
                        ))
        return self._condition_history

    def surgery_history(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return []
        if self._surgery_history is None:
            self._surgery_history = []
            conditions = Condition.objects.committed().for_patient(self.patient_uuid)
            for condition in conditions.filter(clinical_status=ClinicalStatus.RESOLVED):  # TODO add surgical=True
                for coding in condition.codings.all():
                    if coding.system == "ICD-10":
                        self._surgery_history.append(CodedItem(
                            uuid=str(condition.id),
                            label=coding.display,
                            code=Helper.icd10_add_dot(coding.code),
                        ))
        return self._surgery_history

    def existing_questionnaires(self) -> list[CodedItem]:
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                CodedItem(uuid="ooo", label="Medication Adherence", code=""),
                CodedItem(uuid="ppp", label="Tobacco", code=""),
                CodedItem(uuid="qqq", label="Exercise", code=""),
                CodedItem(uuid="rrr", label="Stress", code=""),
                CodedItem(uuid="sss", label="Care Plan", code=""),
            ]
        if self._questionnaires is None:
            self._questionnaires = []
            questionnaires = Questionnaire.objects.filter(
                status="AC",
                can_originate_in_charting=True,
                use_case_in_charting="QUES",
            )
            for questionnaire in questionnaires:
                self._questionnaires.append(CodedItem(
                    uuid=str(questionnaire.id),
                    label=questionnaire.name,
                    code="",
                ))
        return self._questionnaires

    # def patient_birth_date(self) -> date:
    #     if not Constants.HAS_DATABASE_ACCESS:
    #         return date(1993, 4, 17)
    #     if self._patient is None:
    #         self._patient = Patient.objects.get(self.patient_uuid)
    #     return self._patient.birth_date
    #
    # def patient_weight(self) -> str:
    #     if not Constants.HAS_DATABASE_ACCESS:
    #         return "169.3 pounds"
    #     if self._weight is None:
    #         self._weight = "unknown"
    #         weight = Observation.objects.for_patient(
    #             self.patient_uuid).filter(
    #             name="weight", category="vital-signs").order_by(
    #             "-effective_datetime").first()
    #         if weight is not None:
    #             self._weight = f"{weight.value / 16:1.2f} pounds"
    #     return self._weight

    def demographic__str__(self) -> str:
        if not Constants.HAS_DATABASE_ACCESS:
            # return "the patient is a boy, born on April 17, 2013 (age 11) and weight 100.00 pounds"
            return "the patient is a man, born on April 17, 2001 (age 23) and weight 150.00 pounds"

        if self._demographic is None:
            patient = Patient.objects.get(id=self.patient_uuid)

            is_female = bool(patient.sex_at_birth == SexAtBirth.FEMALE)
            dob = patient.birth_date.strftime("%B %d, %Y")
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
            if weight:
                ratio = 1 / 1
                if weight.units == "oz":
                    ratio = 1 / 16
                self._demographic = f"{self._demographic} and weight {int(weight.value) * ratio:1.2f} pounds"

        return self._demographic
