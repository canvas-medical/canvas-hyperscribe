from canvas_sdk.commands.commands.adjust_prescription import AdjustPrescriptionCommand
from canvas_sdk.commands.constants import CodeSystems, ClinicalQuantity
from canvas_sdk.v1.data import Medication

from hyperscribe.handlers.commands.base_prescription import BasePrescription
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem


class AdjustPrescription(BasePrescription):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_ADJUST_PRESCRIPTION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        new_medication = data.get('change_medication_to', {}).get('text')
        old_medication = data.get('prescribe', {}).get('text')

        if old_medication:
            code = str((data.get('prescribe') or {}).get("value") or "")
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

            text = old_medication
            if old_medication != new_medication and new_medication:
                text = f"{old_medication} to {new_medication}"

            return CodedItem(
                label=f"{text}: {sig} (dispense: {quantity_to_dispense}, supply days: {days_supply}, "
                      f"refills: {refills}, substitution: {substitution}, related conditions: {indications})",
                code=code,
                uuid="",
            )
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | AdjustPrescriptionCommand:
        result = AdjustPrescriptionCommand(
            sig=parameters["sig"],
            days_supply=int(parameters["suppliedDays"]),
            substitutions=Helper.enum_or_none(parameters["substitution"], AdjustPrescriptionCommand.Substitutions),
            prescriber_id=self.provider_uuid,
            note_uuid=self.note_uuid,
        )
        if 0 <= (idx := parameters["oldMedicationIndex"]) < len(current := self.cache.current_medications()):
            medication_uuid = current[idx].uuid
            medication = Medication.objects.get(id=medication_uuid)
            coding = medication.codings.filter(system=CodeSystems.FDB).first()
            result.fdb_code = coding.code
            # new_fdb_code and type_to_dispense will be overwritten if the new medication is different
            result.type_to_dispense = ClinicalQuantity(
                representative_ndc=medication.national_drug_code,
                ncpdp_quantity_qualifier_code=medication.potency_unit_code,
            )
            result.new_fdb_code = result.fdb_code

        if (keywords := parameters["keywordsNewMedication"]) not in ["", "SAME"]:
            # retrieve the conditions linked to the prescription
            # TODO when it is provided
            condition = ""
            # retrieve existing medications defined in Canvas Science
            choose_medications = self.medications_from(
                chatter,
                parameters["comment"],
                keywords.split(","),
                condition,
            )
            # find the correct quantity to dispense and refill values
            if choose_medications and (medication := choose_medications[0]):
                self.set_medication_dosage(
                    chatter,
                    parameters["comment"],
                    result,
                    medication,
                )
        return result

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in AdjustPrescriptionCommand.Substitutions])
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.cache.current_medications())])
        return {
            "oldMedication": f"one of: {medications}",
            "oldMedicationIndex": "index of the medication to change, or -1, as integer",
            "keywordsNewMedication": "comma separated keywords of up to 5 synonyms of the new medication to prescribe, or 'SAME' if there is no change of medication",
            "sig": "directions, as free text",
            "suppliedDays": "duration of the treatment in days, as integer",
            "substitution": f"one of: {substitutions}",
            "comment": "rational of the change of prescription, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{medication.label}' for medication in self.cache.current_medications()])
        return (f"Change the prescription of a current medication ({text}), including the new medication, the directions, "
                "the duration and the dosage. There can be only one change of prescription per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{medication.label} (RxNorm: {medication.code})' for medication in self.cache.current_medications()])
        return f"'{self.class_name()}' has to be related to one of the following medications: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_medications())
