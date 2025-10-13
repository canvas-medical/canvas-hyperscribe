from __future__ import annotations

from typing import Any

from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.lab import LabPartnerTest
from django.db.models import Q

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.charge_description import ChargeDescription
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.immunization_cached import ImmunizationCached
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.medication_cached import MedicationCached


class LimitedCache:
    def __init__(self) -> None:
        self._actual_staged_commands: list[Command] = []
        self._coded_staged_commands: dict[str, list[CodedItem]] = {}
        self._instance_settings: dict = {}
        self._allergies: list[CodedItem] = []
        self._condition_history: list[CodedItem] = []
        self._conditions: list[CodedItem] = []
        self._demographic: str = ""
        self._family_history: list[CodedItem] = []
        self._goals: list[CodedItem] = []
        self._immunizations: list[ImmunizationCached] = []
        self._medications: list[MedicationCached] = []
        self._note_type: list[CodedItem] = []
        self._preferred_lab_partner: CodedItem = CodedItem(uuid="", label="", code="")
        self._reason_for_visit: list[CodedItem] = []
        self._roles: list[CodedItem] = []
        self._staff_members: list[CodedItem] = []
        self._surgery_history: list[CodedItem] = []
        self._task_labels: list[CodedItem] = []
        self._teams: list[CodedItem] = []
        self._charge_descriptions: list[ChargeDescription] = []
        self._lab_tests: dict[str, list[CodedItem]] = {}
        self._local_data = False

    @property
    def is_local_data(self) -> bool:
        return self._local_data

    def current_commands(self) -> list[Command]:
        return self._actual_staged_commands

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
        return self._charge_descriptions

    def add_instructions_as_staged_commands(
        self,
        instructions: list[Instruction],
        schema_key2instruction: dict,
    ) -> None:
        # it is not correct to assimilate the Instruction.information to command.label, but this is the closest
        instruction2schema_key = {item: key for key, item in schema_key2instruction.items()}
        for instruction in instructions:
            schema_key = instruction2schema_key[instruction.instruction]
            if schema_key not in self._coded_staged_commands:
                self._coded_staged_commands[schema_key] = []

            for idx in range(len(self._coded_staged_commands[schema_key])):
                command = self._coded_staged_commands[schema_key][idx]
                if command.uuid == instruction.uuid:
                    self._coded_staged_commands[schema_key][idx] = CodedItem(
                        uuid=command.uuid,
                        label=instruction.information,
                        code=command.code,
                    )
                    break
            else:
                self._coded_staged_commands[schema_key].append(
                    CodedItem(uuid=instruction.uuid, label=instruction.information, code=""),
                )

    def staged_commands_of(self, schema_keys: list[str]) -> list[CodedItem]:
        return [
            command
            for key, commands in self._coded_staged_commands.items()
            if key in schema_keys
            for command in commands
        ]

    def staged_commands_as_instructions(self, schema_key2instruction: dict) -> list[Instruction]:
        result: list[Instruction] = []
        counter = 0
        for key, commands in self._coded_staged_commands.items():
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
        return self._goals

    def current_conditions(self) -> list[CodedItem]:
        return self._conditions

    def current_medications(self) -> list[MedicationCached]:
        return self._medications

    def current_immunizations(self) -> list[ImmunizationCached]:
        return self._immunizations

    def current_allergies(self) -> list[CodedItem]:
        return self._allergies

    def family_history(self) -> list[CodedItem]:
        return self._family_history

    def condition_history(self) -> list[CodedItem]:
        return self._condition_history

    def surgery_history(self) -> list[CodedItem]:
        return self._surgery_history

    def existing_note_types(self) -> list[CodedItem]:
        return self._note_type

    def existing_reason_for_visits(self) -> list[CodedItem]:
        return self._reason_for_visit

    def existing_roles(self) -> list[CodedItem]:
        return self._roles

    def existing_staff_members(self) -> list[CodedItem]:
        return self._staff_members

    def existing_task_labels(self) -> list[CodedItem]:
        return self._task_labels

    def existing_teams(self) -> list[CodedItem]:
        return self._teams

    def demographic__str__(self) -> str:
        return self._demographic

    def practice_setting(self, setting: str) -> Any:
        return self._instance_settings[setting]

    def preferred_lab_partner(self) -> CodedItem:
        return self._preferred_lab_partner

    def to_json(self) -> dict:
        return {
            "stagedCommands": {
                key: [i.to_dict() for i in commands] for key, commands in self._coded_staged_commands.items()
            },
            "settings": {
                setting: self.practice_setting(setting)
                for setting in [
                    "preferredLabPartner",
                    "serviceAreaZipCodes",
                ]
            },
            "demographicStr": self.demographic__str__(),
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
