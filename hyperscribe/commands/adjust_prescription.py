from canvas_sdk.commands.commands.adjust_prescription import AdjustPrescriptionCommand
from canvas_sdk.commands.constants import CodeSystems, ClinicalQuantity
from canvas_sdk.v1.data import Medication

from hyperscribe.commands.base_prescription import BasePrescription
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_search import MedicationSearch


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

    def command_from_json(self, instruction: InstructionWithParameters, chatter: LlmBase) -> InstructionWithCommand | None:
        result = AdjustPrescriptionCommand(
            sig=instruction.parameters["sig"],
            days_supply=int(instruction.parameters["suppliedDays"]),
            substitutions=Helper.enum_or_none(instruction.parameters["substitution"], AdjustPrescriptionCommand.Substitutions),
            prescriber_id=self.identification.provider_uuid,
            note_uuid=self.identification.note_uuid,
        )
        if 0 <= (idx := instruction.parameters["oldMedicationIndex"]) < len(current := self.cache.current_medications()):
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

        new_medication = instruction.parameters["newMedication"]
        if bool(new_medication["sameAsCurrent"]) is False:
            # retrieve the conditions linked to the prescription
            # TODO when it is provided
            condition = ""
            # retrieve existing medications defined in Canvas Science
            search = MedicationSearch(
                comment=instruction.parameters["comment"],
                keywords=new_medication["keywords"].split(","),
                brand_names=new_medication["brandNames"].split(","),
                related_condition=condition,
            )
            choose_medications = self.medications_from(instruction, chatter, search)
            # find the correct quantity to dispense and refill values
            if choose_medications and (medication := choose_medications[0]):
                self.set_medication_dosage(
                    instruction,
                    chatter,
                    instruction.parameters["comment"],
                    result,
                    medication,
                )
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in AdjustPrescriptionCommand.Substitutions])
        medications = "/".join([f'{medication.label} (index: {idx})' for idx, medication in enumerate(self.cache.current_medications())])
        return {
            "oldMedication": f"one of: {medications}",
            "oldMedicationIndex": "index of the medication to change, or -1, as integer",
            "newMedication": {
                "keywords": "comma separated keywords of up to 5 synonyms of the new medication to prescribe",
                "brandNames": "comma separated of known medication names related to the keywords",
                "sameAsCurrent": "same medication as current one, mandatory, True or False, as boolean"
            },
            "sig": "directions, as free text",
            "suppliedDays": "duration of the treatment in days, as integer",
            "substitution": f"one of: {substitutions}",
            "comment": "rationale of the change of prescription including all important words, as free text",
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