from canvas_sdk.commands.commands.refill import RefillCommand

from commander.protocols.structures.commands.base import Base


class Refill(Base):
    def command_from_json(self, parameters: dict) -> None | RefillCommand:
        return None

    def command_parameters(self) -> dict:
        return {}

    def instruction_description(self) -> str:
        return ""

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return False
