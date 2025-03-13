from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.handlers.commands.base_prescription import BasePrescription
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.llms.llm_base import LlmBase
from hyperscribe.handlers.structures.coded_item import CodedItem


class Prescription(BasePrescription):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_PRESCRIPTION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if (prescribe := data.get("prescribe")) and (text := prescribe.get("text")):
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
            return CodedItem(
                label=f"{text}: {sig} (dispense: {quantity_to_dispense}, supply days: {days_supply}, "
                      f"refills: {refills}, substitution: {substitution}, indications: {indications})",
                code=code,
                uuid="",
            )
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | PrescribeCommand:
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
                and 0 <= (idx := parameters["conditionIndex"]) < len(self.cache.current_conditions())):
            targeted_condition = self.cache.current_conditions()[idx]
            result.icd10_codes = [Helper.icd10_strip_dot(targeted_condition.code)]
            condition = targeted_condition.label

        # retrieve existing medications defined in Canvas Science
        choose_medications = self.medications_from(
            chatter,
            parameters["comment"],
            parameters["keywords"].split(","),
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
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.cache.current_conditions())])

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
