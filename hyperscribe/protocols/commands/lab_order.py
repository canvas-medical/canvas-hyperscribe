from canvas_sdk.commands.commands.lab_order import LabOrderCommand
from canvas_sdk.v1.data.lab import LabPartner

from hyperscribe.protocols.commands.base import Base
from hyperscribe.protocols.constants import Constants
from hyperscribe.protocols.selector_chat import SelectorChat
from hyperscribe.protocols.structures.coded_item import CodedItem


class LabOrder(Base):

    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_LAB_ORDER

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        fasting = "n/a"
        if "fasting_status" in data:
            fasting = "yes" if data["fasting_status"] is True else "no"
        diagnosis = "/".join([
            diagnose
            for item in (data.get("diagnosis") or [])
            if (diagnose := item.get("text"))
        ]) or "n/a"
        comment = data.get("comment") or "n/a"
        tests = "/".join([
            test
            for item in (data.get("tests") or [])
            if (test := item.get("text"))
        ])

        if tests:
            return CodedItem(label=f"{tests}: {comment} (fasting: {fasting}, diagnosis: {diagnosis})", code="", uuid="")
        return None

    def command_from_json(self, parameters: dict) -> None | LabOrderCommand:
        result = LabOrderCommand(
            ordering_provider_key=self.provider_uuid,
            fasting_required=parameters["fastingRequired"],
            comment=parameters["comment"][:127],  # <-- no more than 128 characters
            note_uuid=self.note_uuid,
            diagnosis_codes=[],
            tests_order_codes=[],
        )
        # retrieve the linked conditions
        conditions = []
        for condition in parameters["conditions"]:
            item = SelectorChat.condition_from(
                self.settings,
                condition["conditionKeywords"].split(","),
                condition["ICD10"].split(","),
                parameters["comment"],
            )
            if item.code:
                conditions.append(item)
                result.diagnosis_codes.append(item.code)

        # ATTENTION: We need to determine the lab vendor in a smarter, dynamic way
        lab_partner = LabPartner.objects.filter(name="Generic Lab").first()
        if lab_partner is not None:
            result.lab_partner = str(lab_partner.id)
            # retrieve the tests based on the keywords
            for lab_order in parameters["labOrders"]:
                item = SelectorChat.lab_test_from(
                    self.settings,
                    lab_partner.name,
                    lab_order["labOrderKeyword"].split(","),
                    parameters["comment"],
                    [c.label for c in conditions],
                )
                if item.code:
                    result.tests_order_codes.append(item.code)

        return result

    def command_parameters(self) -> dict:
        return {
            "labOrders": [
                {
                    "labOrderKeyword": "comma separated keywords of up to 5 synonyms of each lab test to order",
                },
            ],
            "conditions": [
                {
                    "conditionKeywords": "comma separated keywords of up to 5 synonyms of each condition targeted by the lab tests",
                    "ICD10": "comma separated keywords of up to 5 ICD-10 codes of each condition targeted by the lab test",
                },
            ],
            "fastingRequired": "mandatory, True or False, as boolean",
            "comment": "rational of the prescription, as free text limited to 128 characters",
        }

    def instruction_description(self) -> str:
        return ("Lab tests ordered, including the directions and the targeted condition. "
                "There can be several lab orders in an instruction with the fasting requirement for the whole instruction "
                "and all necessary information for each lab order, "
                "and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
