from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Refill(Base):
    @classmethod
    def command_type(cls) -> str:
        return "RefillCommand"

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REFILL

    @classmethod
    def note_section(cls) -> str:
        return Constants.NOTE_SECTION_PLAN

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (prescribe := data.get("prescribe")) and (text := prescribe.get("text")):
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
                code="",
                uuid="",
            )
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = RefillCommand(
            sig=instruction.parameters["sig"],
            days_supply=instruction.parameters["suppliedDays"],
            substitutions=Helper.enum_or_none(instruction.parameters["substitution"], PrescribeCommand.Substitutions),
            prescriber_id=self.identification.provider_uuid,
            note_uuid=self.identification.note_uuid,
        )
        if 0 <= (idx := instruction.parameters["medicationIndex"]) < len(current := self.cache.current_medications()):
            result.fdb_code = current[idx].code_fdb
            result.type_to_dispense = ClinicalQuantity(
                representative_ndc=current[idx].national_drug_code,
                ncpdp_quantity_qualifier_code=current[idx].potency_unit_code,
            )
            self.add_code2description(current[idx].code_fdb, current[idx].label)
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "medication": "",
            "medicationIndex": -1,
            "sig": "",
            "suppliedDays": 0,
            "substitution": "",
            "comment": "",
        }

    def command_parameters_schemas(self) -> list[dict]:
        substitutions = [status.value for status in PrescribeCommand.Substitutions]
        medications = [medication.label for medication in self.cache.current_medications()]
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "medication": {
                            "type": "string",
                            "description": "The medication to refill",
                            "enum": medications,
                        },
                        "medicationIndex": {
                            "type": "integer",
                            "description": "Index of the medication to refill",
                        },
                        "sig": {
                            "type": "string",
                            "description": "Directions, as free text",
                        },
                        "suppliedDays": {
                            "type": "integer",
                            "exclusiveMinimum": 0,
                            "description": "Duration of the treatment in days, at least 1",
                        },
                        "substitution": {
                            "type": "string",
                            "description": "Substitution status for the refill",
                            "enum": substitutions,
                        },
                        "comment": {
                            "type": "string",
                            "description": "Rationale of the prescription, as free text",
                        },
                    },
                    "required": ["medication", "medicationIndex", "sig", "suppliedDays", "substitution", "comment"],
                    "additionalProperties": False,
                },
            }
        ]

    def instruction_description(self) -> str:
        text = ", ".join([f"{medication.label}" for medication in self.cache.current_medications()])
        return (
            f"Refill of a current medication ({text}), including the directions, the duration, "
            f"the targeted condition and the dosage. "
            "Only create when a refill is ordered during this visit, not when discussing refills already sent. "
            "There can be only one refill per instruction, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join(
            [
                f"{medication.label} (RxNorm: {medication.code_rx_norm})"
                for medication in self.cache.current_medications()
            ],
        )
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_medications())
