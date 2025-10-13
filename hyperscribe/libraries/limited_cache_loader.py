from __future__ import annotations

from datetime import date
from typing import Any, Tuple
from typing import Iterable

from canvas_sdk.commands.constants import CodeSystems
from canvas_sdk.v1.data import (
    AllergyIntolerance,
    CareTeamRole,
    ChargeDescriptionMaster,
    Condition,
    Goal,
    Immunization,
    ImmunizationCoding,
    ImmunizationStatement,
    ImmunizationStatementCoding,
    Medication,
    NoteType,
    Observation,
    Patient,
    PracticeLocation,
    ReasonForVisitSettingCoding,
    StaffRole,
    Staff,
    Team,
    TaskLabel,
)
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.condition import ClinicalStatus
from canvas_sdk.v1.data.goal import GoalLifecycleStatus
from canvas_sdk.v1.data.lab import LabPartner
from canvas_sdk.v1.data.medication import Status
from canvas_sdk.v1.data.patient import SexAtBirth
from django.db.models.expressions import When, Value, Case

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.charge_description import ChargeDescription
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.immunization_cached import ImmunizationCached
from hyperscribe.structures.medication_cached import MedicationCached


class LimitedCacheLoader:
    def __init__(self, identification: IdentificationParameters, commands_policy: AccessPolicy, obfuscate: bool):
        self.identification = identification
        self.commands_policy = commands_policy
        self.obfuscate = obfuscate

    @classmethod
    def commands_to_coded_items(
        cls,
        commands: Iterable[Command],
        commands_policy: AccessPolicy,
        use_real_uuids: bool,
    ) -> dict[str, list[CodedItem]]:
        result: dict[str, list[CodedItem]] = {}
        for command in commands:
            for command_class in ImplementedCommands.command_list():
                if (
                    commands_policy.is_allowed(command_class.class_name())
                    and command_class.schema_key() == command.schema_key
                ):
                    if coded_item := command_class.staged_command_extract(command.data):
                        key = command.schema_key
                        if key not in result:
                            result[key] = []
                        result[key].append(
                            CodedItem(
                                uuid=str(command.id) if use_real_uuids else coded_item.uuid,
                                label=coded_item.label,
                                code=coded_item.code,
                            ),
                        )
                    break
        return result

    def current_commands(self) -> list[Command]:
        return [
            command
            for command in Command.objects.filter(
                patient__id=self.identification.patient_uuid,
                note__id=self.identification.note_uuid,
                state="staged",  # <--- TODO use an Enum when provided
            ).order_by("dbid")
        ]

    @classmethod
    def charge_descriptions(cls) -> list[ChargeDescription]:
        if ChargeDescriptionMaster.objects.count() <= Constants.MAX_CHARGE_DESCRIPTIONS:
            # use the last code of any short name duplication
            records = {
                record.short_name: ChargeDescription(
                    short_name=record.short_name,
                    full_name=record.name,
                    cpt_code=record.cpt_code,
                )
                for record in ChargeDescriptionMaster.objects.all().order_by("cpt_code")
            }
            return list(records.values())
        return []

    def retrieve_conditions(self) -> Tuple[list[CodedItem], list[CodedItem], list[CodedItem]]:
        conditions: list[CodedItem] = []
        condition_history: list[CodedItem] = []
        surgery_history: list[CodedItem] = []

        statuses = [ClinicalStatus.ACTIVE, ClinicalStatus.RESOLVED]
        systems = [CodeSystems.ICD10, CodeSystems.SNOMED]
        records = (
            Condition.objects.committed()
            .for_patient(self.identification.patient_uuid)
            .filter(clinical_status__in=statuses)
        )
        for condition in records.order_by("-dbid"):
            case = Case(When(system=CodeSystems.ICD10, then=Value(1)), When(system=CodeSystems.SNOMED, then=Value(2)))
            coding = (
                condition.codings.filter(system__in=systems)
                .annotate(system_order=case)
                .order_by("system_order")
                .first()
            )

            if coding:
                item = CodedItem(uuid=str(condition.id), label=coding.display, code=Helper.icd10_add_dot(coding.code))
                if condition.clinical_status == ClinicalStatus.ACTIVE:
                    conditions.append(item)
                elif condition.clinical_status == ClinicalStatus.RESOLVED and condition.surgical is False:
                    condition_history.append(item)
                elif condition.clinical_status == ClinicalStatus.RESOLVED and condition.surgical is True:
                    surgery_history.append(item)
        return conditions, condition_history, surgery_history

    def current_goals(self) -> list[CodedItem]:
        # ATTENTION below code should not be used since there is no way to know if a goal is already closed
        # TODO should use the `committed` method
        #  waiting for https://github.com/canvas-medical/canvas-plugins/discussions/1066
        goals = Goal.objects.filter(
            patient__id=self.identification.patient_uuid,
            lifecycle_status__in=[
                GoalLifecycleStatus.PROPOSED,
                GoalLifecycleStatus.PLANNED,
                GoalLifecycleStatus.ACCEPTED,
                GoalLifecycleStatus.ACTIVE,
                GoalLifecycleStatus.ON_HOLD,
            ],
            committer_id__isnull=False,
            entered_in_error_id__isnull=True,
        ).order_by("-dbid")

        return [
            CodedItem(
                uuid=str(goal.id),
                label=goal.goal_statement,
                # TODO code should be "",
                #  waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
                code=str(goal.dbid),
            )
            for goal in goals
        ]

    def current_medications(self) -> list[MedicationCached]:
        result: list[MedicationCached] = []
        medications = (
            Medication.objects.committed().for_patient(self.identification.patient_uuid).filter(status=Status.ACTIVE)
        )
        for medication in medications.order_by("-dbid"):
            label = ""
            code_rx_norm = ""
            code_fdb = ""
            for coding in medication.codings.all():
                if coding.system == CodeSystems.RXNORM:
                    label = coding.display
                    code_rx_norm = coding.code
                if coding.system == CodeSystems.FDB:
                    label = coding.display
                    code_fdb = coding.code

            result.append(
                MedicationCached(
                    uuid=str(medication.id),
                    label=label,
                    code_rx_norm=code_rx_norm,
                    code_fdb=code_fdb,
                    national_drug_code=medication.national_drug_code,
                    potency_unit_code=medication.potency_unit_code,
                ),
            )
        return result

    @classmethod
    def immunization_from(
        cls,
        record_uuid: str,
        comments: str,
        approximate_date: date | None,
        coding_records: list[ImmunizationStatementCoding | ImmunizationCoding],
    ) -> ImmunizationCached:
        label = code_cvx = code_cpt = ""
        for coding in coding_records:
            if coding.system == CodeSystems.CVX:
                label = coding.display
                code_cvx = coding.code
            if coding.system == CodeSystems.CPT:
                label = coding.display
                code_cpt = coding.code
        return ImmunizationCached(
            uuid=record_uuid,
            label=label,
            code_cvx=code_cvx,
            code_cpt=code_cpt,
            comments=comments,
            approximate_date=approximate_date,
        )

    def current_immunizations(self) -> list[ImmunizationCached]:
        result: list[ImmunizationCached] = []
        # TODO waiting for https://github.com/canvas-medical/canvas-plugins/issues/1067
        immunizations = Immunization.objects.for_patient(self.identification.patient_uuid).filter(deleted=False)
        # immunizations = Immunization.objects.committed().for_patient(self.identification.patient_uuid)
        for immunization in immunizations.order_by("-dbid"):
            result.append(
                self.immunization_from(
                    str(immunization.id),
                    immunization.sig_original,
                    immunization.note.datetime_of_service.date(),
                    immunization.codings.all(),
                )
            )
        # TODO waiting for https://github.com/canvas-medical/canvas-plugins/issues/1067
        statements = ImmunizationStatement.objects.for_patient(self.identification.patient_uuid).filter(deleted=False)
        # statements = ImmunizationStatement.objects.committed().for_patient(self.identification.patient_uuid)
        for statement in statements.order_by("-dbid"):
            result.append(
                self.immunization_from(
                    str(statement.id),
                    statement.comment,
                    statement.date,
                    # TODO should be `codings`,
                    #  waiting for https://github.com/canvas-medical/canvas-plugins/issues/1068
                    statement.coding.all(),
                )
            )

        return result

    def current_allergies(self) -> list[CodedItem]:
        result: list[CodedItem] = []
        allergies = (
            AllergyIntolerance.objects.committed()
            .for_patient(self.identification.patient_uuid)
            .filter(status=Status.ACTIVE)
        )
        for allergy in allergies.order_by("-dbid"):
            for coding in allergy.codings.all():
                if coding.system == CodeSystems.FDB:
                    result.append(CodedItem(uuid=str(allergy.id), label=coding.display, code=coding.code))
        return result

    @classmethod
    def family_history(cls) -> list[CodedItem]:
        return []

    @classmethod
    def existing_note_types(cls) -> list[CodedItem]:
        note_types = NoteType.objects.filter(
            is_active=True,
            is_visible=True,
            is_scheduleable=True,
        ).order_by(
            "-dbid",
        )
        return [
            CodedItem(uuid=str(note_type.id), label=note_type.name, code=note_type.code) for note_type in note_types
        ]

    @classmethod
    def existing_reason_for_visits(cls) -> list[CodedItem]:
        return [
            CodedItem(uuid=str(rfv.id), label=rfv.display, code=rfv.code)
            for rfv in ReasonForVisitSettingCoding.objects.order_by("-dbid")
        ]

    def existing_roles(self) -> list[CodedItem]:
        return [
            CodedItem(uuid=str(role.dbid), label=f"{role.display}", code="")
            for role in CareTeamRole.objects.filter(care_teams__patient__id=self.identification.patient_uuid).distinct()
        ]

    @classmethod
    def existing_staff_members(cls) -> list[CodedItem]:
        results: list[CodedItem] = []
        for staff in Staff.objects.filter(active=True).order_by("last_name"):
            label = f"{staff.first_name} {staff.last_name}"
            if role := staff.top_clinical_role:
                role_type = StaffRole.RoleType(role.role_type).label
                domain = StaffRole.RoleDomain(role.domain).label
                label = f"{label} ({domain}/{role_type})"
            results.append(CodedItem(uuid=str(staff.dbid), label=label, code=""))
        return results

    @classmethod
    def existing_task_labels(cls) -> list[CodedItem]:
        return [
            CodedItem(uuid=str(task.dbid), label=task.name, code="")
            for task in TaskLabel.objects.filter(active=True).order_by("name")
        ]

    @classmethod
    def existing_teams(cls) -> list[CodedItem]:
        return [CodedItem(uuid=str(team.dbid), label=team.name, code="") for team in Team.objects.order_by("name")]

    def demographic__str__(self) -> str:
        patient = Patient.objects.get(id=self.identification.patient_uuid)

        is_female = bool(patient.sex_at_birth == SexAtBirth.FEMALE)
        dob = patient.birth_date.strftime("%B %d, %Y")
        if self.obfuscate:
            dob = "<DOB REDACTED>"  # principal of minimum disclosure
        today = date.today()
        age = (
            today.year
            - patient.birth_date.year
            - ((today.month, today.day) < (patient.birth_date.month, patient.birth_date.day))
        )
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

        result = f"the patient is a {sex_at_birth}, born on {dob} (age {age_str})"

        weight = (
            Observation.objects.for_patient(self.identification.patient_uuid)
            .filter(name="weight", category="vital-signs")
            .order_by("-effective_datetime")
            .first()
        )
        if weight and weight.value:
            ratio = 1 / 1
            if weight.units == "oz":
                ratio = 1 / 16

            result = f"{result} and weight {int(weight.value) * ratio:1.2f} pounds"

        return result

    def practice_setting(self, setting: str) -> Any:
        practice = None
        if staff := Staff.objects.filter(id=self.identification.provider_uuid).first():
            practice = staff.primary_practice_location
        if practice is None:
            practice = PracticeLocation.objects.order_by("dbid").first()
        if practice and (value := practice.settings.filter(name=setting).order_by("dbid").first()):
            return value.value
        return None

    def preferred_lab_partner(self) -> CodedItem:
        lab_partner_uuid = ""
        preferred_lab = self.practice_setting("preferredLabPartner")
        lab_partner = LabPartner.objects.filter(name=preferred_lab).first()
        if lab_partner is not None:
            lab_partner_uuid = str(lab_partner.id)
        return CodedItem(uuid=lab_partner_uuid, label=preferred_lab, code="")

    def load_from_database(self) -> LimitedCache:
        result = LimitedCache()
        commands = self.current_commands()
        result._actual_staged_commands = commands
        result._coded_staged_commands = self.commands_to_coded_items(
            commands,
            self.commands_policy,
            not self.obfuscate,
        )
        result._instance_settings = {
            setting: self.practice_setting(setting) for setting in ["preferredLabPartner", "serviceAreaZipCodes"]
        }
        result._allergies = self.current_allergies()
        result._conditions, result._condition_history, result._surgery_history = self.retrieve_conditions()
        result._demographic = self.demographic__str__()
        result._family_history = self.family_history()
        result._goals = self.current_goals()
        result._immunizations = self.current_immunizations()
        result._medications = self.current_medications()
        result._note_type = self.existing_note_types()
        result._preferred_lab_partner = self.preferred_lab_partner()
        result._reason_for_visit = self.existing_reason_for_visits()
        result._roles = self.existing_roles()
        result._staff_members = self.existing_staff_members()
        result._task_labels = self.existing_task_labels()
        result._teams = self.existing_teams()
        result._charge_descriptions = self.charge_descriptions()
        result._lab_tests = {}
        result._local_data = False

        return result

    @classmethod
    def load_from_json(cls, cache: dict) -> LimitedCache:
        result = LimitedCache()
        result._actual_staged_commands = []
        result._coded_staged_commands = {
            key: [
                CodedItem.load_from_json(cmd | {"uuid": f"xyz{idx * 1000 + num:04d}"})
                for num, cmd in enumerate(commands)
            ]
            for idx, (key, commands) in enumerate(cache.get("stagedCommands", {}).items())
        }
        result._instance_settings = cache.get(
            "settings",
            {
                "preferredLabPartner": "",
                "serviceAreaZipCodes": [],
            },
        )
        result._allergies = CodedItem.load_from_json_list(cache.get("currentAllergies", []))
        result._condition_history = CodedItem.load_from_json_list(cache.get("conditionHistory", []))
        result._conditions = CodedItem.load_from_json_list(cache.get("currentConditions", []))
        result._demographic = cache.get("demographicStr", "")
        result._family_history = CodedItem.load_from_json_list(cache.get("familyHistory", []))
        result._goals = CodedItem.load_from_json_list(cache.get("currentGoals", []))
        result._immunizations = ImmunizationCached.load_from_json_list(cache.get("currentImmunization", []))
        result._medications = MedicationCached.load_from_json_list(cache.get("currentMedications", []))
        result._note_type = CodedItem.load_from_json_list(cache.get("existingNoteTypes", []))
        result._preferred_lab_partner = CodedItem.load_from_json(
            cache.get(
                "preferredLabPartner",
                {"uuid": "", "label": "", "code": ""},
            )
        )
        result._reason_for_visit = CodedItem.load_from_json_list(cache.get("existingReasonForVisit", []))
        result._roles = CodedItem.load_from_json_list(cache.get("existingRoles", []))
        result._staff_members = CodedItem.load_from_json_list(cache.get("existingStaffMembers", []))
        result._surgery_history = CodedItem.load_from_json_list(cache.get("surgeryHistory", []))
        result._task_labels = CodedItem.load_from_json_list(cache.get("existingTaskLabels", []))
        result._teams = CodedItem.load_from_json_list(cache.get("existingTeams", []))
        result._charge_descriptions = [ChargeDescription.load_from_json(i) for i in cache.get("chargeDescriptions", [])]
        result._lab_tests = {}
        result._local_data = True

        return result
