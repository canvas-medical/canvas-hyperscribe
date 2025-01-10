from canvas_sdk.commands.commands.allergy import AllergyCommand, Allergen, AllergenType

from commander.protocols.structures.commands.base import Base


class Allergy(Base):
    def from_json(self, parameters: dict) -> None | AllergyCommand:
        concept_type = AllergenType(1)
        if parameters["type"] == "medication":
            concept_type = AllergenType(2)
        elif parameters["type"] == "ingredient":
            concept_type = AllergenType(6)

        allergy = Allergen(
            concept_id=1,  # TODO retrieve the concept_id with ontologies
            concept_type=concept_type,
        )
        return AllergyCommand(
            # allergy=allergy,
            severity=AllergyCommand.Severity(parameters["severity"]),
            narrative=parameters["reaction"],
            approximate_date=self.str2date(parameters["approximateDateOfOnset"]).date(),
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        severity = "/".join([status.value for status in AllergyCommand.Severity])
        return {
            "allergy": "name of the component responsible fo the allergy",
            "type": "allergen/medication/ingredient",
            "severity": severity,
            "reaction": "description of the reaction as free text",
            "approximateDateOfOnset": "YYYY-MM-DD",
        }

    def information(self) -> str:
        return ("Any known allergy, one instruction per allergy. "
                "There can be only one allergy per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
