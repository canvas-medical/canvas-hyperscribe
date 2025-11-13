from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.commands.base_prescription import BasePrescription
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_search import MedicationSearch


class Prescription(BasePrescription):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PRESCRIPTION

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (prescribe := data.get("prescribe")) and (text := prescribe.get("text")):
            code = str((data.get("prescribe") or {}).get("value") or "")
            sig = data.get("sig") or "n/a"
            refills = data.get("refills") or "n/a"
            quantity_to_dispense = data.get("quantity_to_dispense") or "n/a"
            days_supply = data.get("days_supply") or "n/a"
            substitution = data.get("substitutions") or "n/a"
            indications = (
                "/".join(
                    [
                        indication
                        for question in (data.get("indications") or [])
                        if (indication := question.get("text"))
                    ],
                )
                or "n/a"
            )
            return CodedItem(
                label=f"{text}: {sig} (dispense: {quantity_to_dispense}, supply days: {days_supply}, "
                f"refills: {refills}, substitution: {substitution}, related conditions: {indications})",
                code=code,
                uuid="",
            )
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = PrescribeCommand(
            sig=instruction.parameters["sig"],
            days_supply=int(instruction.parameters["suppliedDays"]),
            substitutions=Helper.enum_or_none(instruction.parameters["substitution"], PrescribeCommand.Substitutions),
            prescriber_id=self.identification.provider_uuid,
            note_uuid=self.identification.note_uuid,
        )
        # identified the condition, if any
        condition = ""
        if (
            "conditionIndex" in instruction.parameters
            and isinstance(instruction.parameters["conditionIndex"], int)
            and 0 <= (idx := instruction.parameters["conditionIndex"]) < len(self.cache.current_conditions())
        ):
            targeted_condition = self.cache.current_conditions()[idx]
            result.icd10_codes = [Helper.icd10_strip_dot(targeted_condition.code)]
            condition = targeted_condition.label
            self.add_code2description(targeted_condition.code, targeted_condition.label)

        # retrieve existing medications defined in Canvas Science
        search = MedicationSearch(
            comment=instruction.parameters["comment"],
            keywords=instruction.parameters["keywords"].split(","),
            brand_names=instruction.parameters["medicationNames"].split(","),
            related_condition=condition,
        )
        choose_medications = self.medications_from(instruction, chatter, search)
        # find the correct quantity to dispense and refill values
        if choose_medications and (medication := choose_medications[0]):
            self.set_medication_dosage(instruction, chatter, instruction.parameters["comment"], result, medication)
            self.add_code2description(medication.fdb_code, medication.description)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        result: dict = {
            "keywords": "",
            "medicationNames": "",
            "sig": "",
            "suppliedDays": 0,
            "substitution": "",
            "comment": "",
        }
        if self.cache.current_conditions():
            result |= {
                "condition": "",
                "conditionIndex": -1,
            }
        return result

    def command_parameters_schemas(self) -> list[dict]:
        substitutions = [status.value for status in PrescribeCommand.Substitutions]
        conditions = [condition.label for condition in self.cache.current_conditions()]
        fields: dict = {
            "keywords": {
                "type": "string",
                "description": "Comma separated list of up to 5 relevant drugs to consider prescribing",
            },
            "medicationNames": {
                "type": "string",
                "description": "Comma separated list of known medication names, generics "
                "and brands, related to the keywords",
            },
            "sig": {
                "type": "string",
                "description": "Directions as stated; if specific frequency mentioned "
                "(e.g. 'once weekly', 'twice daily'), preserve it exactly, as free text",
            },
            "suppliedDays": {
                "type": "integer",
                "exclusiveMinimum": 0,
                "description": "Duration of the treatment in days either as mentioned, "
                "or following the standard practices, at least 1",
            },
            "substitution": {
                "type": "string",
                "description": "Substitution status for the prescription, "
                f"default is '{PrescribeCommand.Substitutions.ALLOWED.value}'",
                "enum": substitutions,
            },
            "comment": {
                "type": "string",
                "description": "Rationale of the prescription including all mentioned details: "
                "medication name/brand, specific strength if stated (e.g. '2.5 mg', '10 mg'), "
                "route, and specific frequency if stated (e.g. 'once weekly', 'twice daily'), "
                "as free text",
            },
        }
        required_fields: list[str] = ["keywords", "medicationNames", "sig", "suppliedDays", "substitution", "comment"]
        if conditions:
            fields |= {
                "condition": {
                    "type": ["string", "null"],
                    "description": "The condition for which the medication is prescribed, "
                    "or null if not related to any condition",
                    "enum": conditions + [None],
                },
                "conditionIndex": {
                    "type": "integer",
                    "description": "Index of the condition for which the medication is prescribed, "
                    "or -1 if the prescription is not related to any listed condition",
                },
            }
            required_fields.extend(["condition", "conditionIndex"])

        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": fields,
                    "required": required_fields,
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        return (
            "New prescription order, including the medication, the directions, the duration, the targeted condition "
            "and the dosage. Create as many instructions as necessary as there can be only one prescribed item per "
            "instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return f'"{self.class_name()}" supports only one prescribed item per instruction.'

    def is_available(self) -> bool:
        return True
