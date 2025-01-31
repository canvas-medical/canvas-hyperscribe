from canvas_sdk.commands.commands.assess import AssessCommand
from canvas_sdk.commands.commands.remove_allergy import RemoveAllergyCommand

from commander.protocols.commands.base import Base


class RemoveAllergy(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "removeAllergy"

    def command_from_json(self, parameters: dict) -> None | AssessCommand:
        allergy_uuid = ""
        if 0 <= (idx := parameters["allergyIndex"]) < len(self.current_allergies()):
            allergy_uuid = self.current_allergies()[idx].uuid
        return RemoveAllergyCommand(
            allergy_id=allergy_uuid,
            narrative=parameters["narrative"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        allergies = "/".join([f'{allergy.label} (index: {idx})' for idx, allergy in enumerate(self.current_allergies())])
        return {
            "allergies": f"one of: {allergies}",
            "allergyIndex": "Index of the allergy to remove, as integer",
            "narrative": "explanation of why the allergy is removed, as free text",
        }

    def instruction_description(self) -> str:
        return ("Remove a previously diagnosed allergy. "
                "There can be only one allergy, with the explanation, to remove per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if self.current_allergies():
            text = ", ".join([allergy.label for allergy in self.current_allergies()])
            result = f"'{self.class_name()}' has to be related to one of the following allergies: {text}."
        return result

    def is_available(self) -> bool:
        return True
