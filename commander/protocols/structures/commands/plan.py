from canvas_sdk.commands.commands.plan import PlanCommand

from commander.protocols.structures.commands.base import Base


class Plan(Base):
    def from_json(self, parameters: dict) -> PlanCommand:
        return PlanCommand(
            narrative=parameters["plan"],
        )

    def parameters(self) -> dict:
        return {
            "plan": "free text",
        }

    def information(self) -> str:
        return ("Defined plan for future patient visits. "
                "There can be only one plan per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
