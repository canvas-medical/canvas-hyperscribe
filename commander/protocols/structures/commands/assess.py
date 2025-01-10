from canvas_sdk.commands.commands.assess import AssessCommand

from commander.protocols.structures.commands.base import Base


class Assess(Base):

    def from_json(self, parameters: dict) -> AssessCommand:
        condition_id = ""
        if 0 <= (idx := parameters["conditionIndex"]) < len(self.current_conditions()):
            condition_id = (self.current_conditions()[idx]["uuid"])
        return AssessCommand(
            condition_id=condition_id,
            background=parameters["background"],
            status=AssessCommand.Status(parameters["status"]),
            narrative=parameters["narrative"],
        )

    def parameters(self) -> dict:
        statuses = "/".join([status.value for status in AssessCommand.Status])
        conditions = "/".join([f'{condition["label"]} (index: {idx})' for idx, condition in enumerate(self.current_conditions())])
        return {
            "condition": conditions,
            "conditionIndex": "Index of the Condition to assess",
            "background": "free text",
            "status": statuses,
            "narrative": "free text",
        }

    def information(self) -> str:
        text = [
            f'* {condition["label"]} (ICD-10: {condition["code"]})'
            for condition in self.current_conditions()
        ]
        text.insert(0, "Assessment of a diagnosed condition limited to:")
        text.append("There can be only one assessment per condition per instruction, and no instruction in the lack of.")
        return "\n".join(text)

    def is_available(self) -> bool:
        return bool(self.current_conditions())
