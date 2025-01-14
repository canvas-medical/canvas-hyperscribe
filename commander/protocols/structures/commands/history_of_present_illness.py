from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from commander.protocols.structures.commands.base import Base


class HistoryOfPresentIllness(Base):
    def from_json(self, parameters: dict) -> None | HistoryOfPresentIllnessCommand:
        return HistoryOfPresentIllnessCommand(
            narrative=parameters["narrative"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "narrative": "free text",
        }

    def information(self) -> str:
        return ("Provider's reported key highlights of the visit. "
                "There can be multiple highlights within an instruction.")

    def constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
