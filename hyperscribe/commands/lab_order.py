from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class LabOrder(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_LAB_ORDER

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        fasting = "n/a"
        if "fasting_status" in data:
            fasting = "yes" if data["fasting_status"] is True else "no"

        list_diagnosis = data.get("diagnosis") or []
        if isinstance(list_diagnosis, str):
            list_diagnosis = []

        diagnosis = "/".join([diagnose for item in list_diagnosis if (diagnose := item.get("text"))]) or "n/a"
        comment = data.get("comment") or "n/a"
        if tests := data.get("tests"):
            if not isinstance(tests, list):
                return None  # <-- waiting for https://github.com/canvas-medical/canvas/issues/17567
            descriptions = "/".join([test for item in tests if (test := item.get("text"))])
            return CodedItem(
                label=f"{descriptions}: {comment} (fasting: {fasting}, diagnosis: {diagnosis})",
                code="",
                uuid="",
            )
        return None

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = LabOrderCommand(
            ordering_provider_key=self.identification.provider_uuid,
            fasting_required=bool(instruction.parameters["fastingRequired"]),
            comment=instruction.parameters["comment"][:127],  # <-- no more than 128 characters
            note_uuid=self.identification.note_uuid,
            diagnosis_codes=[],
            tests_order_codes=[],
        )
        # retrieve the linked conditions
        conditions = []
        for condition in instruction.parameters["conditions"]:
            item = SelectorChat.condition_from(
                instruction,
                chatter,
                self.settings,
                condition["conditionKeywords"].split(","),
                condition["ICD10"].split(","),
                instruction.parameters["comment"],
            )
            if item.code:
                conditions.append(item)
                result.diagnosis_codes.append(item.code)

        lab_partner = self.cache.preferred_lab_partner()
        if lab_partner.uuid:
            result.lab_partner = lab_partner.uuid
            # retrieve the tests based on the keywords
            for lab_order in instruction.parameters["labOrders"]:
                item = SelectorChat.lab_test_from(
                    instruction,
                    chatter,
                    self.cache,
                    lab_partner.label,
                    lab_order["labOrderKeywords"].split(","),
                    instruction.parameters["comment"],
                    [c.label for c in conditions],
                )
                if item.code:
                    result.tests_order_codes.append(item.code)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "labOrders": [
                {"labOrderKeywords": "comma separated keywords of up to 5 synonyms of each lab test to order"},
            ],
            "conditions": [
                {
                    "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition "
                    "targeted by the lab tests",
                    "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition targeted "
                    "by the lab test",
                },
            ],
            "fastingRequired": "mandatory, True or False, as boolean",
            "comment": "rationale of the prescription, as free text limited to 128 characters",
        }

    def instruction_description(self) -> str:
        return (
            "Lab tests ordered, including the directions and the targeted conditions. "
            "There can be several lab orders in an instruction with the fasting requirement for the whole instruction "
            "and all necessary information for each lab order, "
            "and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
