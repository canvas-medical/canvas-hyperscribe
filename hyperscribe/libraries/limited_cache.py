from __future__ import annotations

from datetime import date
from typing import Any

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
from canvas_sdk.v1.data.condition import ClinicalStatus
from canvas_sdk.v1.data.goal import GoalLifecycleStatus
from canvas_sdk.v1.data.lab import LabPartner
from canvas_sdk.v1.data.lab import LabPartnerTest
from canvas_sdk.v1.data.medication import Status
from canvas_sdk.v1.data.patient import SexAtBirth
from django.db.models import Q
from django.db.models.expressions import When, Value, Case

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.structures.charge_description import ChargeDescription
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.immunization_cached import ImmunizationCached
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.medication_cached import MedicationCached


class LimitedCache:
    def __init__(
        self,
        patient_uuid: str,
        provider_uuid: str,
        staged_commands_to_coded_items: dict[str, list[CodedItem]],
    ):
        self.patient_uuid = patient_uuid
        self.provider_uuid = provider_uuid
        self._settings: dict = {}
        self._allergies: list[CodedItem] | None = None
        self._condition_history: list[CodedItem] | None = None
        self._conditions: list[CodedItem] | None = None
        self._demographic: str | None = None
        self._family_history: list[CodedItem] | None = None
        self._goals: list[CodedItem] | None = None
        self._immunizations: list[ImmunizationCached] | None = None
        self._medications: list[MedicationCached] | None = None
        self._note_type: list[CodedItem] | None = None
        self._preferred_lab_partner: CodedItem | None = None
        self._reason_for_visit: list[CodedItem] | None = None
        self._roles: list[CodedItem] | None = None
        self._staff_members: list[CodedItem] | None = None
        self._surgery_history: list[CodedItem] | None = None
        self._task_labels: list[CodedItem] | None = None
        self._teams: list[CodedItem] | None = None
        self._staged_commands: dict[str, list[CodedItem]] = staged_commands_to_coded_items
        self._charge_descriptions: list[ChargeDescription] | None = None
        self._lab_tests: dict[str, list[CodedItem]] = {}
        self._local_data = False

    @property
    def is_local_data(self) -> bool:
        return self._local_data

    def lab_tests(self, lab_partner: str, keywords: list[str]) -> list[CodedItem]:
        key = " ".join(sorted(keywords))
        if key not in self._lab_tests:
            self._lab_tests[key] = []
            if self._local_data:
                from pathlib import Path
                import sqlite3  # <-- the import is forbidden in the plugin context

                with sqlite3.connect(Path(__file__).parent / Constants.SQLITE_LAB_TESTS_DATABASE) as conn:
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    parameters: dict = {}
                    sql = "SELECT `dbid`, `order_code`, `order_name` FROM `generic_lab_test` WHERE 1=1 "
                    for idx, kw in enumerate(keywords):
                        param = f"kw_{idx:02d}"
                        sql += f" AND `keywords` LIKE :{param}"
                        parameters[param] = f"%{kw}%"
                    sql += " ORDER BY `dbid`"
                    cursor.execute(sql, parameters)
                    for row in cursor.fetchall():
                        self._lab_tests[key].append(CodedItem(uuid="", label=row["order_name"], code=row["order_code"]))
            else:
                keyword_q = Q()
                for kw in keywords:
                    keyword_q &= Q(keywords__icontains=kw)
                query = LabPartnerTest.objects.filter(lab_partner__name=lab_partner).filter(keyword_q)
                for test in query:
                    self._lab_tests[key].append(CodedItem(uuid="", label=test.order_name, code=test.order_code))
        return self._lab_tests[key]

    def charge_descriptions(self) -> list[ChargeDescription]:
        if self._charge_descriptions is None:
            self._charge_descriptions = []
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
                self._charge_descriptions = list(records.values())
        return self._charge_descriptions

    def retrieve_conditions(self) -> None:
        self._conditions = []
        self._condition_history = []
        self._surgery_history = []
        statuses = [ClinicalStatus.ACTIVE, ClinicalStatus.RESOLVED]
        systems = [CodeSystems.ICD10, CodeSystems.SNOMED]
        conditions = Condition.objects.committed().for_patient(self.patient_uuid).filter(clinical_status__in=statuses)
        for condition in conditions.order_by("-dbid"):
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
                    self._conditions.append(item)
                elif condition.clinical_status == ClinicalStatus.RESOLVED and condition.surgical is False:
                    self._condition_history.append(item)
                elif condition.clinical_status == ClinicalStatus.RESOLVED and condition.surgical is True:
                    self._surgery_history.append(item)

    def add_instructions_as_staged_commands(
        self,
        instructions: list[Instruction],
        schema_key2instruction: dict,
    ) -> None:
        # it is not correct to assimilate the Instruction.information to command.label, but this is the closest
        instruction2schema_key = {item: key for key, item in schema_key2instruction.items()}
        for instruction in instructions:
            schema_key = instruction2schema_key[instruction.instruction]
            if schema_key not in self._staged_commands:
                self._staged_commands[schema_key] = []

            for idx in range(len(self._staged_commands[schema_key])):
                command = self._staged_commands[schema_key][idx]
                if command.uuid == instruction.uuid:
                    self._staged_commands[schema_key][idx] = CodedItem(
                        uuid=command.uuid,
                        label=instruction.information,
                        code=command.code,
                    )
                    break
            else:
                self._staged_commands[schema_key].append(
                    CodedItem(uuid=instruction.uuid, label=instruction.information, code=""),
                )

    def staged_commands_of(self, schema_keys: list[str]) -> list[CodedItem]:
        return [
            command for key, commands in self._staged_commands.items() if key in schema_keys for command in commands
        ]

    def staged_commands_as_instructions(self, schema_key2instruction: dict) -> list[Instruction]:
        result: list[Instruction] = []
        counter = 0
        for key, commands in self._staged_commands.items():
            for command in commands:
                counter = counter + 1
                result.append(
                    Instruction(
                        uuid=command.uuid,
                        index=counter,
                        instruction=schema_key2instruction[key],
                        information=command.label,
                        is_new=True,
                        is_updated=False,
                    ),
                )
        return result

    def current_goals(self) -> list[CodedItem]:
        if self._goals is None:
            self._goals = []
            # ATTENTION below code should not be used since there is no way to know if a goal is already closed
            # TODO should use the `committed` method
            #  waiting for https://github.com/canvas-medical/canvas-plugins/discussions/1066
            goals = Goal.objects.filter(
                patient__id=self.patient_uuid,
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
            for goal in goals:
                self._goals.append(
                    CodedItem(
                        uuid=str(goal.id),
                        label=goal.goal_statement,
                        # TODO code should be "",
                        #  waiting for https://github.com/canvas-medical/canvas-plugins/issues/338
                        code=str(goal.dbid),
                    ),
                )
        return self._goals

    def current_conditions(self) -> list[CodedItem]:
        if self._conditions is None:
            self.retrieve_conditions()
        return self._conditions or []

    def current_medications(self) -> list[MedicationCached]:
        if self._medications is None:
            self._medications = []
            medications = Medication.objects.committed().for_patient(self.patient_uuid).filter(status=Status.ACTIVE)
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

                self._medications.append(
                    MedicationCached(
                        uuid=str(medication.id),
                        label=label,
                        code_rx_norm=code_rx_norm,
                        code_fdb=code_fdb,
                        national_drug_code=medication.national_drug_code,
                        potency_unit_code=medication.potency_unit_code,
                    ),
                )
        return self._medications

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
        if self._immunizations is None:
            self._immunizations = []
            # TODO waiting for https://github.com/canvas-medical/canvas-plugins/issues/1067
            immunizations = Immunization.objects.for_patient(self.patient_uuid).filter(deleted=False)
            # immunizations = Immunization.objects.committed().for_patient(self.patient_uuid)
            for immunization in immunizations.order_by("-dbid"):
                print("--->", immunization.note.datetime_of_service.date())
                self._immunizations.append(
                    self.immunization_from(
                        str(immunization.id),
                        immunization.sig_original,
                        immunization.note.datetime_of_service.date(),
                        immunization.codings.all(),
                    )
                )
            # TODO waiting for https://github.com/canvas-medical/canvas-plugins/issues/1067
            statements = ImmunizationStatement.objects.for_patient(self.patient_uuid).filter(deleted=False)
            # statements = ImmunizationStatement.objects.committed().for_patient(self.patient_uuid)
            for statement in statements.order_by("-dbid"):
                self._immunizations.append(
                    self.immunization_from(
                        str(statement.id),
                        statement.comment,
                        statement.date,
                        # TODO should be `codings`,
                        #  waiting for https://github.com/canvas-medical/canvas-plugins/issues/1068
                        statement.coding.all(),
                    )
                )

        return self._immunizations

    def current_allergies(self) -> list[CodedItem]:
        if self._allergies is None:
            self._allergies = []
            allergies = (
                AllergyIntolerance.objects.committed().for_patient(self.patient_uuid).filter(status=Status.ACTIVE)
            )
            for allergy in allergies.order_by("-dbid"):
                for coding in allergy.codings.all():
                    if coding.system == CodeSystems.FDB:
                        self._allergies.append(CodedItem(uuid=str(allergy.id), label=coding.display, code=coding.code))
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

    def existing_note_types(self) -> list[CodedItem]:
        if self._note_type is None:
            self._note_type = []
            note_types = NoteType.objects.filter(is_active=True, is_visible=True, is_scheduleable=True).order_by(
                "-dbid",
            )
            for note_type in note_types:
                self._note_type.append(CodedItem(uuid=str(note_type.id), label=note_type.name, code=note_type.code))
        return self._note_type

    def existing_reason_for_visits(self) -> list[CodedItem]:
        if self._reason_for_visit is None:
            self._reason_for_visit = []
            for rfv in ReasonForVisitSettingCoding.objects.order_by("-dbid"):
                self._reason_for_visit.append(CodedItem(uuid=str(rfv.id), label=rfv.display, code=rfv.code))
        return self._reason_for_visit

    def existing_roles(self) -> list[CodedItem]:
        if self._roles is None:
            self._roles = []
            for role in CareTeamRole.objects.filter(care_teams__patient__id=self.patient_uuid).distinct():
                self._roles.append(CodedItem(uuid=str(role.dbid), label=f"{role.display}", code=""))
        return self._roles

    def existing_staff_members(self) -> list[CodedItem]:
        if self._staff_members is None:
            self._staff_members = []
            for staff in Staff.objects.filter(active=True).order_by("last_name"):
                label = f"{staff.first_name} {staff.last_name}"
                if role := staff.top_clinical_role:
                    role_type = StaffRole.RoleType(role.role_type).label
                    domain = StaffRole.RoleDomain(role.domain).label
                    label = f"{label} ({domain}/{role_type})"
                self._staff_members.append(CodedItem(uuid=str(staff.dbid), label=label, code=""))
        return self._staff_members

    def existing_task_labels(self) -> list[CodedItem]:
        if self._task_labels is None:
            self._task_labels = []
            for task in TaskLabel.objects.filter(active=True).order_by("name"):
                self._task_labels.append(CodedItem(uuid=str(task.dbid), label=task.name, code=""))
        return self._task_labels

    def existing_teams(self) -> list[CodedItem]:
        if self._teams is None:
            self._teams = []
            for team in Team.objects.order_by("name"):
                self._teams.append(CodedItem(uuid=str(team.dbid), label=team.name, code=""))
        return self._teams

    def demographic__str__(self, obfuscate: bool) -> str:
        if self._demographic is None:
            patient = Patient.objects.get(id=self.patient_uuid)

            is_female = bool(patient.sex_at_birth == SexAtBirth.FEMALE)
            dob = patient.birth_date.strftime("%B %d, %Y")
            if obfuscate:
                dob = "<DOB REDACTED>"  # principal of minimum disclosure
            today = date.today()
            age = (
                today.year
                - patient.birth_date.year
                - ((today.month, today.day) < (patient.birth_date.month, patient.birth_date.day))
            )
            age_str = str(age)
            if age < 2:
                age_str = (
                    f"{(today.year - patient.birth_date.year) * 12 + today.month - patient.birth_date.month} months"
                )
                sex_at_birth = "baby girl" if is_female else "baby boy"
            elif age < 20:
                sex_at_birth = "girl" if is_female else "boy"
            elif age > 65:
                sex_at_birth = "elderly woman" if is_female else "elderly man"
            else:
                sex_at_birth = "woman" if is_female else "man"

            self._demographic = f"the patient is a {sex_at_birth}, born on {dob} (age {age_str})"

            weight = (
                Observation.objects.for_patient(self.patient_uuid)
                .filter(name="weight", category="vital-signs")
                .order_by("-effective_datetime")
                .first()
            )
            if weight and weight.value:
                ratio = 1 / 1
                if weight.units == "oz":
                    ratio = 1 / 16

                self._demographic = f"{self._demographic} and weight {int(weight.value) * ratio:1.2f} pounds"

        return self._demographic

    def practice_setting(self, setting: str) -> Any:
        if setting not in self._settings:
            self._settings[setting] = None

            practice = None
            if staff := Staff.objects.filter(id=self.provider_uuid).first():
                practice = staff.primary_practice_location
            if practice is None:
                practice = PracticeLocation.objects.order_by("dbid").first()
            if practice and (value := practice.settings.filter(name=setting).order_by("dbid").first()):
                self._settings[setting] = value.value
        return self._settings[setting]

    def preferred_lab_partner(self) -> CodedItem:
        if self._preferred_lab_partner is None:
            lab_partner_uuid = ""
            preferred_lab = self.practice_setting("preferredLabPartner")
            lab_partner = LabPartner.objects.filter(name=preferred_lab).first()
            if lab_partner is not None:
                lab_partner_uuid = str(lab_partner.id)
            self._preferred_lab_partner = CodedItem(uuid=lab_partner_uuid, label=preferred_lab, code="")
        return self._preferred_lab_partner

    def to_json(self, obfuscate: bool) -> dict:
        return {
            "stagedCommands": {key: [i.to_dict() for i in commands] for key, commands in self._staged_commands.items()},
            "settings": {
                setting: self.practice_setting(setting)
                for setting in [
                    "preferredLabPartner",
                    "serviceAreaZipCodes",
                ]
            },  # force the setting fetch
            "demographicStr": self.demographic__str__(obfuscate),
            #
            "conditionHistory": [i.to_dict() for i in self.condition_history()],
            "currentAllergies": [i.to_dict() for i in self.current_allergies()],
            "currentConditions": [i.to_dict() for i in self.current_conditions()],
            "currentGoals": [i.to_dict() for i in self.current_goals()],
            "currentImmunization": [i.to_dict() for i in self.current_immunizations()],
            "currentMedications": [i.to_dict() for i in self.current_medications()],
            "existingNoteTypes": [i.to_dict() for i in self.existing_note_types()],
            "existingReasonForVisit": [i.to_dict() for i in self.existing_reason_for_visits()],
            "existingRoles": [i.to_dict() for i in self.existing_roles()],
            "existingStaffMembers": [i.to_dict() for i in self.existing_staff_members()],
            "existingTaskLabels": [i.to_dict() for i in self.existing_task_labels()],
            "existingTeams": [i.to_dict() for i in self.existing_teams()],
            "familyHistory": [i.to_dict() for i in self.family_history()],
            "preferredLabPartner": self.preferred_lab_partner().to_dict(),
            "surgeryHistory": [i.to_dict() for i in self.surgery_history()],
            "chargeDescriptions": [i.to_dict() for i in self.charge_descriptions()],
            "labTests": {},
        }

    @classmethod
    def load_from_json(cls, cache: dict) -> LimitedCache:
        staged_commands = {
            key: [
                CodedItem.load_from_json(cmd | {"uuid": f"xyz{idx * 1000 + num:04d}"})
                for num, cmd in enumerate(commands)
            ]
            for idx, (key, commands) in enumerate(cache.get("stagedCommands", {}).items())
        }

        result = cls(Constants.FAUX_PATIENT_UUID, Constants.FAUX_PROVIDER_UUID, staged_commands)
        result._demographic = cache.get("demographicStr", "")
        result._settings = cache.get("settings", {})

        result._condition_history = CodedItem.load_from_json_list(cache.get("conditionHistory", []))
        result._allergies = CodedItem.load_from_json_list(cache.get("currentAllergies", []))
        result._conditions = CodedItem.load_from_json_list(cache.get("currentConditions", []))
        result._goals = CodedItem.load_from_json_list(cache.get("currentGoals", []))
        result._immunizations = ImmunizationCached.load_from_json_list(cache.get("currentImmunization", []))
        result._medications = MedicationCached.load_from_json_list(cache.get("currentMedications", []))
        result._note_type = CodedItem.load_from_json_list(cache.get("existingNoteTypes", []))
        result._reason_for_visit = CodedItem.load_from_json_list(cache.get("existingReasonForVisit", []))
        result._roles = CodedItem.load_from_json_list(cache.get("existingRoles", []))
        result._staff_members = CodedItem.load_from_json_list(cache.get("existingStaffMembers", []))
        result._task_labels = CodedItem.load_from_json_list(cache.get("existingTaskLabels", []))
        result._teams = CodedItem.load_from_json_list(cache.get("existingTeams", []))
        result._family_history = CodedItem.load_from_json_list(cache.get("familyHistory", []))
        result._preferred_lab_partner = CodedItem.load_from_json(
            cache.get(
                "preferredLabPartner",
                {"uuid": "", "label": "", "code": ""},
            )
        )
        result._surgery_history = CodedItem.load_from_json_list(cache.get("surgeryHistory", []))

        result._charge_descriptions = [ChargeDescription.load_from_json(i) for i in cache.get("chargeDescriptions", [])]
        result._lab_tests = {}
        result._local_data = True

        return result
