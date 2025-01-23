from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from commander.protocols.structures.commands.base import Base


class LabOrder(Base):
    def command_from_json(self, parameters: dict) -> None | LabOrderCommand:
        result: None | LabOrderCommand = None
        condition_icd10s: list[str] = []
        prompt_condition = ""
        if "conditionIndex" in parameters and isinstance(parameters["conditionIndex"], list):
            len_conditions = len(self.current_conditions())
            targeted_conditions: list = []
            for idx in parameters["conditionIndex"]:
                if isinstance(idx, int) and 0 <= idx < len_conditions:
                    condition = self.current_conditions()[idx]
                    targeted_conditions.append(condition.label)
                    condition_icd10s.append(self.icd10_strip_dot(condition.code))
            prompt_condition = f"The prescription is intended to the patient's conditions: {', '.join(targeted_conditions)}."

        return result

    def command_parameters(self) -> dict:
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])

        condition_dict = {}
        if conditions:
            condition_dict = {
                "condition": f"comma separated list of any of: {conditions}, or empty",
                "conditionIndex": "list of the indexes of the conditions for which the lab test is ordered, as integers",
            }

        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the lab test to order",
            "fastingRequired": f"mandatory, True or False, as boolean",
            "comment": "rational of the prescription, as free text",
        } | condition_dict

    def instruction_description(self) -> str:
        return ("Lab tests ordered, including the directions, if it requires fasting, and the targeted condition. "
                "There can be only one lab order per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
