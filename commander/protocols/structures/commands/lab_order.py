from canvas_sdk.commands.commands.lab_order import LabOrderCommand

from commander.protocols.structures.commands.base import Base


class LabOrder(Base):
    def command_from_json(self, parameters: dict) -> None | LabOrderCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
