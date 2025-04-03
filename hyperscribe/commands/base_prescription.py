import json

from canvas_sdk.commands import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand, Decimal
from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.commands.base import Base
from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_search import MedicationSearch


class BasePrescription(Base):

    def medications_from(self, chatter: LlmBase, search: MedicationSearch) -> list[MedicationDetail]:
        result: list[MedicationDetail] = []
        if medications := CanvasScience.medication_details(self.settings.science_host, search.brand_names):
            prompt_condition = ""
            if search.related_condition:
                prompt_condition = f'The prescription is intended to the patient\'s condition: {search.related_condition}.'

            allergies = '\n * '.join([
                a.label
                for a in
                self.cache.current_allergies() +
                self.cache.staged_commands_of([Constants.SCHEMA_KEY_ALLERGY])
            ])
            if allergies:
                prompt_allergy = f"the patient is allergic to:\n * {allergies}"
            else:
                prompt_allergy = "the patient's medical record contains no information about allergies"

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
                f"keywords: {', '.join(search.keywords)}",
                " -- ",
                search.comment,
                "```",
                "",
                prompt_condition,
                "",
                "The choice of the medication has to also take into account that:",
                f" - {self.cache.demographic__str__()},",
                f" - {prompt_allergy}.",
                "",
                "Among the following medications, identify the most appropriate option:",
                "",
                "\n".join(f' * {medication.description} (fdbCode: {medication.fdb_code})' for medication in medications),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"fdbCode": "the fdb code, as int", "description": "the description"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_fdb_code"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas):
                fdb_code = str(response[0]["fdbCode"])
                result = [m for m in medications if m.fdb_code == fdb_code]

        return result

    def set_medication_dosage(self, chatter: LlmBase, comment: str, command: PrescribeCommand | AdjustPrescriptionCommand,
                              medication: MedicationDetail) -> None:
        quantity = medication.quantities[0]  # ATTENTION forced to the first option (only for simplicity 2025-01-14)

        if isinstance(command, AdjustPrescriptionCommand):
            command.new_fdb_code = medication.fdb_code
        else:  # if isinstance(command, PrescribeCommand):
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
            f"The exact quantities and refill have to also take into account that {self.cache.demographic__str__()}.",
            "",
            "Please, present your findings in a JSON format within a Markdown code block like:",
            "```json",
            json.dumps([{
                "quantityToDispense": "mandatory, quantity to dispense, as float",
                "refills": "mandatory, refills allowed, as integer",
                "noteToPharmacist": "note to the pharmacist, as free text",
                "informationToPatient": "directions to the patient on how to use the medication, specifying the quantity, "
                                        "the form (e.g. tablets, drops, puffs, etc), the frequency and/or max daily frequency, "
                                        "and the route of use (e.g. by mouth, applied to skin, dropped in eye, etc), as free text",
            }]),
            "```",
            "",
        ]
        schemas = JsonSchema.get(["prescription_dosage"])
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas):
            command.quantity_to_dispense = Decimal(response[0]["quantityToDispense"]).quantize(Decimal('0.01'))
            command.refills = int(response[0]["refills"])
            command.note_to_pharmacist = response[0]["noteToPharmacist"]
            command.sig = response[0]["informationToPatient"]
