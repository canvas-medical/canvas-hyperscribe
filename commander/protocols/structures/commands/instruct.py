from canvas_sdk.commands.commands.instruct import InstructCommand

from commander.protocols.structures.commands.base import Base


class Instruct(Base):
    def from_json(self, parameters: dict) -> None | InstructCommand:
        return InstructCommand(
            instruction="Advice to read information",
            comment=f'{parameters["direction"]} - {parameters["comment"]}',
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "direction": "medical name of the immunization and its CPT code",
            "comment": "directions as free text",
        }

    def information(self) -> str:
        return ("Specific or standard direction. "
                "There can be only one direction per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
