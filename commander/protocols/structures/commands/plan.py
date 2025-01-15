from canvas_sdk.commands.commands.plan import PlanCommand

from commander.protocols.structures.commands.base import Base


class Plan(Base):
    def command_from_json(self, parameters: dict) -> None | PlanCommand:
        return PlanCommand(
            narrative=parameters["plan"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        return {
            "plan": "free text",
        }

    def instruction_description(self) -> str:
        return ("Defined plan for future patient visits. "
                "There can be only one plan per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
