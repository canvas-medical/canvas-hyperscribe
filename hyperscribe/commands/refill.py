from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity, CodeSystems
from canvas_sdk.v1.data import Medication

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class Refill(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_REFILL

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (prescribe := data.get("prescribe")) and (text := prescribe.get("text")):
            sig = data.get('sig') or "n/a"
            refills = data.get('refills') or "n/a"
            quantity_to_dispense = data.get('quantity_to_dispense') or "n/a"
            days_supply = data.get('days_supply') or "n/a"
            substitution = data.get('substitutions') or "n/a"
            indications = "/".join([
                indication
                for question in (data.get("indications") or [])
                if (indication := question.get("text"))
            ]) or "n/a"
            return CodedItem(
                label=f"{text}: {sig} (dispense: {quantity_to_dispense}, supply days: {days_supply}, "
                      f"refills: {refills}, substitution: {substitution}, related conditions: {indications})",
                code="",
                uuid="",
            )
        return None

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        result = RefillCommand(
            sig=instruction.parameters["sig"],
            days_supply=instruction.parameters["suppliedDays"],
            substitutions=Helper.enum_or_none(instruction.parameters["substitution"], PrescribeCommand.Substitutions),
            prescriber_id=self.identification.provider_uuid,
            note_uuid=self.identification.note_uuid,
        )
        if 0 <= (idx := instruction.parameters["medicationIndex"]) < len(current := self.cache.current_medications()):
            medication_uuid = current[idx].uuid
            medication = Medication.objects.get(id=medication_uuid)
            coding = medication.codings.filter(system=CodeSystems.FDB).first()

            result.fdb_code = coding.code
            result.type_to_dispense = ClinicalQuantity(
                representative_ndc=medication.national_drug_code,
                ncpdp_quantity_qualifier_code=medication.potency_unit_code,
            )
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.cache.current_medications())])
        return {
            "medication": f"one of: {medications}",
            "medicationIndex": "index of the medication to refill, as integer",
            "sig": "directions, as free text",
            "suppliedDays": "duration of the treatment in days, as integer",
            "substitution": f"one of: {substitutions}",
            "comment": "rationale of the prescription, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{medication.label}' for medication in self.cache.current_medications()])
        return (f"Refill of a current medication ({text}), including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one refill per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{medication.label} (RxNorm: {medication.code})' for medication in self.cache.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_medications())
