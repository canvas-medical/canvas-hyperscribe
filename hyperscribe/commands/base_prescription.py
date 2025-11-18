import json

from canvas_sdk.commands import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand, Decimal
from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_search import MedicationSearch


class BasePrescription(Base):
    def medications_from(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
        search: MedicationSearch,
    ) -> list[MedicationDetail]:
        result: list[MedicationDetail] = []
        if medications := CanvasScience.medication_details(search.brand_names):
            prompt_condition = ""
            if search.related_condition:
                prompt_condition = (
                    f"The prescription is intended to the patient's condition: {search.related_condition}."
                )

            allergies = "\n * ".join(
                [
                    a.label
                    for a in self.cache.current_allergies()
                    + self.cache.staged_commands_of([Constants.SCHEMA_KEY_ALLERGY])
                ],
            )
            if allergies:
                prompt_allergy = f"the patient is allergic to:\n * {allergies}"
            else:
                prompt_allergy = "the patient's medical record contains no information about allergies"

            # retrieve the correct medication
            system_prompt = [
                "Medical context: select the single most relevant medication from the list.",
                "CRITICAL: If specific medication name and/or dose is mentioned, you MUST select exact match only.",
                "",
            ]
            user_prompt = [
                "Provider data:",
                "```text",
                f"keywords: {', '.join(search.keywords)}",
                search.comment,
                "```",
                "",
                prompt_condition,
                "",
                "Consider:",
                f" - {self.cache.demographic__str__(False)}",
                f" - {prompt_allergy}",
                "",
                "Medications:",
                "\n".join(
                    f" * {medication.description} (fdbCode: {medication.fdb_code})" for medication in medications
                ),
                "",
                "IMPORTANT: If specific name and/or dose mentioned, select exact match. "
                "Do not substitute different name or dose.",
                "",
                "Return the ONE most relevant medication as JSON in Markdown code block:",
                "```json",
                json.dumps([{"fdbCode": "int", "description": "description"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_fdb_code"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                fdb_code = str(response[0]["fdbCode"])
                result = [m for m in medications if m.fdb_code == fdb_code]

        return result

    def set_medication_dosage(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
        comment: str,
        command: PrescribeCommand | AdjustPrescriptionCommand,
        medication: MedicationDetail,
    ) -> None:
        quantity = medication.quantities[0]  # ATTENTION forced to the first option (only for simplicity 2025-01-14)

        if isinstance(command, AdjustPrescriptionCommand):
            command.new_fdb_code = medication.fdb_code
        else:  # if isinstance(command, PrescribeCommand):
            command.fdb_code = medication.fdb_code

        command.type_to_dispense = ClinicalQuantity(
            representative_ndc=quantity.representative_ndc,
            ncpdp_quantity_qualifier_code=quantity.ncpdp_quantity_qualifier_code,
        )

        schemas = JsonSchema.get(["prescription_dosage"])
        system_prompt = [
            "Medical context: compute quantity to dispense and refills for prescription.",
            "CRITICAL: If specific frequency mentioned (e.g. 'once weekly', 'twice daily'), "
            "you MUST preserve exact frequency in directions.",
            "",
        ]
        user_prompt = [
            f"Provider prescription comment for {medication.description}:",
            "```text",
            comment,
            "```",
            "",
            f"Medication form: {quantity.quantity}, {quantity.ncpdp_quantity_qualifier_description}.",
            f"Supply days: {command.days_supply}",
            f"Patient: {self.cache.demographic__str__(False)}",
            "",
            "Calculate quantity to dispense and refills for the supply days.",
            "",
            "IMPORTANT: If specific frequency mentioned, preserve exact frequency in informationToPatient. "
            "Calculate quantity based on stated frequency.",
            "",
            "Return as JSON in Markdown code block:",
            "```json",
            json.dumps(
                [
                    {
                        "quantityToDispense": -1,
                        "refills": -1,
                        "discreteQuantity": True,
                        "noteToPharmacist": "",
                        "informationToPatient": "",
                    },
                ],
            ),
            "```",
            "",
            "Validate with schema:",
            "```json",
            json.dumps(schemas[0]),
            "```",
            "",
        ]
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            quantity = Decimal(response[0]["quantityToDispense"])
            is_discrete = response[0]["discreteQuantity"]

            # For discrete quantities (tablets, capsules, etc.), use integer format
            # For continuous quantities (liquids, creams, etc.), use decimal format
            if is_discrete:
                command.quantity_to_dispense = Decimal(int(quantity))
            else:
                command.quantity_to_dispense = quantity.quantize(Decimal("0.01"))

            command.refills = int(response[0]["refills"])
            command.note_to_pharmacist = response[0]["noteToPharmacist"]
            command.sig = response[0]["informationToPatient"]
