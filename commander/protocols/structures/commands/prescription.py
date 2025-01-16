from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.constants import ClinicalQuantity

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class Prescription(Base):
    def command_from_json(self, parameters: dict) -> None | PrescribeCommand:
        result: None | PrescribeCommand = None
        condition_icd10s: list[str] = []
        prompt_condition = ""
        if isinstance(parameters["conditionIndex"], int) and 0 <= (idx := parameters["conditionIndex"]) < len(self.current_conditions()):
            targeted_condition = self.current_conditions()[idx]
            condition_icd10s.append(self.icd10_strip_dot(targeted_condition.code))
            prompt_condition = f'The prescription is intended to the patient\'s condition: {targeted_condition.label}.'

        # retrieve existing medications defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        medications = CanvasScience.medication_details(self.settings.science_host, expressions)

        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        # retrieve the correct medication
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the prescription:',
            '```text',
            parameters["comment"],
            '```',
            "",
            prompt_condition,
            "",
            'Among the following medications, identify the most relevant one:',
            '',
            "\n".join(f' * {medication.description} (fdbCode: {medication.fdb_code})' for medication in medications),
            '',
            'Please present your findings in a JSON format within a Markdown code block like',
            '```json',
            '[{"fdbCode": "the fdb code, as int", "description": "the description"]'
            '```',
            '',
        ]
        response = conversation.chat()
        choose_medications = []
        if response.has_error is False and response.content:
            fdb_code = str(response.content[0]["fdbCode"])
            choose_medications = [m for m in medications if m.fdb_code == fdb_code]

        # find the correct quantity to dispense and refill values
        if choose_medications and (medication := choose_medications[0]):
            quantity = medication.quantities[0]  # ATTENTION forced to the first option (only for simplicity 2025-01-14)
            result = PrescribeCommand(
                fdb_code=medication.fdb_code,
                icd10_codes=condition_icd10s[:2],  # <--- no more than 2 conditions
                sig=parameters["sig"],
                days_supply=parameters["suppliedDays"],
                type_to_dispense=ClinicalQuantity(
                    representative_ndc=quantity.representative_ndc,
                    ncpdp_quantity_qualifier_code=quantity.ncpdp_quantity_qualifier_code,
                ),
                substitutions=PrescribeCommand.Substitutions(parameters["substitution"]),
                prescriber_id=self.provider_uuid,
                note_uuid=self.note_uuid,
            )
            conversation.system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to compute the quantity to dispense and the number of refills for a prescription.",
                "",
            ]

            conversation.user_prompt = [
                f'Here is the comment provided by the healthcare provider in regards to the prescription of '
                f'the medication {medication.description}:',
                '```text',
                parameters["comment"],
                '```',
                "",
                f"The medication is provided as {quantity.quantity}, {quantity.ncpdp_quantity_qualifier_description}.",
                "",
                "Based on this information, what are the quantity to dispense and the number of refills in order to "
                f"fulfill the {result.days_supply} supply days?",
                '',
                'Please present your findings in a JSON format within a Markdown code block like',
                '```json',
                '[{"quantityToDispense": 0, "refills": 0, "noteToPharmacist": "note to the pharmacist, as free text"}]'
                '```',
                '',
            ]
            response = conversation.chat()
            if response.has_error is False and response.content:
                result.quantity_to_dispense = response.content[0]["quantityToDispense"]
                result.refills = response.content[0]["refills"]
                result.note_to_pharmacist = response.content[0]["noteToPharmacist"]

        return result

    def command_parameters(self) -> dict:
        substitutions = "/".join([status.value for status in PrescribeCommand.Substitutions])
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the medication to prescribe",
            "condition": f"None or, one of: {conditions}",  # ATTENTION limiting to only one condition even if the UI accepts up to 2 conditions
            "conditionIndex": "index of the condition for which the medication is prescribed, as integer or None if the prescription is not related to any provided condition",
            "sig": "directions, as free text",
            "suppliedDays": "duration of the treatment in days, as integer",
            # "quantityToDispense": 0,
            # "refills": 0,
            "substitution": f"one of: {substitutions}",
            "comment": "rational of the prescription, as free text",
            # "noteToPharmacist": "note to the pharmacist, as free text",
        }

    def instruction_description(self) -> str:
        return ("Medication prescription, including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one prescription per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
