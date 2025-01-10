from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from commander.protocols.structures.commands.base import Base


class FamilyHistory(Base):
    def from_json(self, parameters: dict) -> FamilyHistoryCommand:
        return FamilyHistoryCommand(
            family_history=parameters["condition"],
            relative=parameters["relative"],
            note=f'{parameters["note"]} - {parameters["condition"]}',
        )

    def parameters(self) -> dict:
        return {
            "condition": "medical name of the condition",
            "relative": "father/mother/parent/child/brother/sister/sibling/grand-parent/grand-father/grand-mother",
            "note": "free text",
        }

    def information(self) -> str:
        return ("Any relevant condition of a close relative (father, mother, parent, child, brother, sister, sibling, grand-parent, grand-father, grand-mother). "
                "There can be only one condition per relative per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
