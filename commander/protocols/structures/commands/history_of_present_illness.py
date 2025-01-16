from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from commander.protocols.structures.commands.base import Base


class HistoryOfPresentIllness(Base):
    def command_from_json(self, parameters: dict) -> None | HistoryOfPresentIllnessCommand:
        return HistoryOfPresentIllnessCommand(
            narrative=parameters["narrative"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        return {
            "narrative": "highlights of the visit from the provider point of view, as free text",
        }

    def instruction_description(self) -> str:
        return ("Provider's reported key highlights of the visit. "
                "There can be multiple highlights within an instruction.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
