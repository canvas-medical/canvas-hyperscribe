import json

from canvas_sdk.commands.commands.prescribe import PrescribeCommand, Decimal
from canvas_sdk.commands.constants import ClinicalQuantity

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.helper import Helper
from commander.protocols.structures.medication_detail import MedicationDetail


class Prescription(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "prescribe"

    def medications_from(self, comment: str, keywords: list[str], condition: str) -> list[MedicationDetail]:
        result: list[MedicationDetail] = []
        if medications := CanvasScience.medication_details(self.settings.science_host, keywords):
            prompt_condition = ""
            if condition:
                prompt_condition = f'The prescription is intended to the patient\'s condition: {condition}.'
            # retrieve the correct medication
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the prescription:",
                "```text",
                f"keywords: {', '.join(keywords)}",
                " -- ",
                comment,
                "```",
                "",
                prompt_condition,
                "",
                f"The choice of the medication has to also take into account that {self.demographic__str__()}.",
                "",
                "Among the following medications, identify the most relevant one:",
                "",
                "\n".join(f' * {medication.description} (fdbCode: {medication.fdb_code})' for medication in medications),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"fdbCode": "the fdb code, as int", "description": "the description"}]),
                "```",
                "",
            ]
            if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt):
                fdb_code = str(response[0]["fdbCode"])
                result = [m for m in medications if m.fdb_code == fdb_code]

        return result

    def set_medication_dosage(self, comment: str, command: PrescribeCommand, medication: MedicationDetail) -> None:
        quantity = medication.quantities[0]  # ATTENTION forced to the first option (only for simplicity 2025-01-14)

        command.fdb_code = medication.fdb_code
        command.type_to_dispense = ClinicalQuantity(
            representative_ndc=quantity.representative_ndc,
            ncpdp_quantity_qualifier_code=quantity.ncpdp_quantity_qualifier_code,
        )

        system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to compute the quantity to dispense and the number of refills for a prescription.",
            "",
        ]
        user_prompt = [
            "Here is the comment provided by the healthcare provider in regards to the prescription of "
            f"the medication {medication.description}:",
            "```text",
            comment,
            "```",
            "",
            f"The medication is provided as {quantity.quantity}, {quantity.ncpdp_quantity_qualifier_description}.",
            "",
            "Based on this information, what are the quantity to dispense and the number of refills in order to "
            f"fulfill the {command.days_supply} supply days?",
            "",
            f"The exact quantities and refill have to also take into account that {self.demographic__str__()}.",
            "",
            "Please, present your findings in a JSON format within a Markdown code block like:",
            "```json",
            json.dumps([{
                "quantityToDispense": "mandatory, quantity to dispense, as decimal",
                "refills": "mandatory, refills allowed, as integer",
                "noteToPharmacist": "note to the pharmacist, as free text",
                "informationToPatient": "directions to the patient on how to use the medication, specifying the quantity, "
                                        "the form (e.g. tablets, drops, puffs, etc), the frequency and/or max daily frequency, "
                                        "and the route of use (e.g. by mouth, applied to skin, dropped in eye, etc), as free text",
            }]),
            "```",
            "",
        ]
        if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt):
            # TODO should be Decimal, waiting for https://github.com/canvas-medical/canvas-plugins/discussions/332
            command.quantity_to_dispense = Decimal(response[0]["quantityToDispense"]).quantize(Decimal('0.01'))
            command.refills = int(response[0]["refills"])
            command.note_to_pharmacist = response[0]["noteToPharmacist"]
            command.sig = response[0]["informationToPatient"]

    def command_from_json(self, parameters: dict) -> None | PrescribeCommand:
        result = PrescribeCommand(
            sig=parameters["sig"],
            days_supply=int(parameters["suppliedDays"]),
            substitutions=Helper.enum_or_none(parameters["substitution"], PrescribeCommand.Substitutions),
            prescriber_id=self.provider_uuid,
            note_uuid=self.note_uuid,
        )
        # identified the condition, if any
        condition = ""
        if ("conditionIndex" in parameters
                and isinstance(parameters["conditionIndex"], int)
                and 0 <= (idx := parameters["conditionIndex"]) < len(self.current_conditions())):
            targeted_condition = self.current_conditions()[idx]
            result.icd10_codes = [Helper.icd10_strip_dot(targeted_condition.code)]
            condition = targeted_condition.label

        # retrieve existing medications defined in Canvas Science
        choose_medications = self.medications_from(
            parameters["comment"],
            parameters["keywords"].split(","),
            condition,
        )
        # find the correct quantity to dispense and refill values
        if choose_medications and (medication := choose_medications[0]):
            self.set_medication_dosage(parameters["comment"], result, medication)

        return result

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])

        condition_dict = {}
        if conditions:
            condition_dict = {
                "condition": f"None or, one of: {conditions}",  # ATTENTION limiting to only one condition even if the UI accepts up to 2 conditions
                "conditionIndex": "index of the condition for which the medication is prescribed, as integer or -1 if the prescription is not related to any listed condition",
            }

        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the medication to prescribe",
            "sig": "directions, as free text",
            "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following the standard practices, as integer",
            # "quantityToDispense": 0,
            # "refills": 0,
            "substitution": f"one of: {substitutions}",
            "comment": "rational of the prescription, as free text",
            # "noteToPharmacist": "note to the pharmacist, as free text",
        } | condition_dict

    def instruction_description(self) -> str:
        return ("Medication prescription, including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one prescription per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
