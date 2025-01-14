from canvas_sdk.commands.commands.instruct import InstructCommand

from commander.protocols.structures.commands.base import Base


class Immunize(Base):
    def from_json(self, parameters: dict) -> None | InstructCommand:
        # TODO change to ImmunizeCommand when implemented
        return InstructCommand(
            instruction="Advice to read information",
            comment=f'{parameters["sig"]} - {parameters["immunize"]}',
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "immunize": "medical name of the immunization and its CPT code",
            "sig": "directions as free text",
        }

    def information(self) -> str:
        return ("Immunization or vaccine to be administered. "
                "There can be only one immunization per instruction, and no instruction in the lack of.")

    def constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
