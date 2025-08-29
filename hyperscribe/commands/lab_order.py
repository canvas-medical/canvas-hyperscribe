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
        self.add_code2description(self.identification.provider_uuid, "")
        # retrieve the linked conditions
        conditions = []
        for condition in instruction.parameters["conditions"]:
            item = SelectorChat.condition_from(
                instruction,
                chatter,
                condition["conditionKeywords"].split(","),
                condition["ICD10"].split(","),
                instruction.parameters["comment"],
            )
            if item.code:
                conditions.append(item)
                result.diagnosis_codes.append(item.code)
                self.add_code2description(item.code, item.label)

        lab_partner = self.cache.preferred_lab_partner()
        if lab_partner.uuid:
            result.lab_partner = lab_partner.uuid
            self.add_code2description(lab_partner.uuid, lab_partner.label)

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
                    self.add_code2description(item.code, item.label)

        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        return {
            "labOrders": [],
            "conditions": [],
            "fastingRequired": "mandatory, True or False, as boolean",
            "comment": "rationale of the prescription, as free text limited to 128 characters",
        }

    def command_parameters_schemas(self) -> list[dict]:
        return [
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "array",
                "minItems": 1,
                "maxItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "labOrders": {
                            "type": "array",
                            "minItems": 1,
                            "description": "List of each requested lab order.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "labOrderName": {
                                        "type": "string",
                                        "description": "the common name of the requested lab test.",
                                    },
                                    "labOrderKeywords": {
                                        "type": "string",
                                        "description": "Comma-separated keywords to find the specific lab test in a "
                                        "database (using OR criteria), it is better to provide "
                                        "more specific keywords rather than few broad ones.",
                                    },
                                },
                                "required": ["labOrderName", "labOrderKeywords"],
                                "additionalProperties": False,
                            },
                        },
                        "conditions": {
                            "type": "array",
                            "minItems": 0,
                            "description": "List of conditions explicitly mentioned as related to the lab orders."
                            "The list has to be empty if no condition is provided in the transcript.",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "conditionName": {
                                        "type": "string",
                                        "description": "the common name of the condition targeted by the lab tests.",
                                    },
                                    "conditionKeywords": {
                                        "type": "string",
                                        "description": "Comma-separated keywords to find in a database "
                                        "(using OR criteria) the condition targeted by the lab tests.",
                                    },
                                    "ICD10": {
                                        "type": "string",
                                        "description": "Comma-separated ICD-10 codes (up to 5) for the condition",
                                    },
                                },
                                "required": ["conditionKeywords", "ICD10"],
                                "additionalProperties": False,
                            },
                        },
                        "fastingRequired": {
                            "type": "boolean",
                            "description": "Whether fasting is required prior to the lab test",
                        },
                        "comment": {
                            "type": "string",
                            "description": "Rationale for the prescription as explicitly explained in the transcript",
                            "maxLength": 128,
                        },
                    },
                    "required": ["labOrders", "conditions", "fastingRequired", "comment"],
                    "additionalProperties": False,
                },
            }
        ]

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
