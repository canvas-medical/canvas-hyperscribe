import json

from canvas_sdk.commands.commands.allergy import AllergyCommand, Allergen, AllergenType

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.helper import Helper


class Allergy(Base):

    @classmethod
    def schema_key(cls) -> str:
        return "allergy"

    def command_from_json(self, parameters: dict) -> None | AllergyCommand:
        concept_types = [AllergenType(1)]  # <-- always include the Allergy Group
        if parameters["type"] == "medication":
            concept_types.append(AllergenType(2))
        elif parameters["type"] == "ingredient":
            concept_types.append(AllergenType(6))

        # retrieve existing allergies defined in Canvas Ontologies
        expressions = parameters["keywords"].split(",")
        allergies = CanvasScience.search_allergy(
            self.settings.ontologies_host,
            self.settings.pre_shared_key,
            expressions,
            concept_types,
        )
        result = AllergyCommand(
            severity=Helper.enum_or_none(parameters["severity"], AllergyCommand.Severity),
            narrative=parameters["reaction"],
            approximate_date=Helper.str2date(parameters["approximateDateOfOnset"]),
            note_uuid=self.note_uuid,
        )
        if allergies:
            # retrieve the correct allergy
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant allergy of a patient out of a list of allergies.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the allergy:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                f'severity: {parameters["severity"]}',
                "",
                parameters["reaction"],
                '```',
                "",
                'Among the following allergies, identify the most relevant one:',
                '',
                "\n".join(f' * {allergy.concept_id_description} (conceptId: {allergy.concept_id_value})' for allergy in allergies),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"conceptId": "the concept id, as int", "description": "the description"}]),
                '```',
                '',
            ]
            if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt):
                concept_id = int(response[0]["conceptId"])
                allergy = [
                    allergy
                    for allergy in allergies
                    if allergy.concept_id_value == concept_id
                ][0]
                result.allergy = Allergen(
                    concept_id=concept_id,
                    concept_type=AllergenType(allergy.concept_id_type),
                )
        return result

    def command_parameters(self) -> dict:
        severity = "/".join([status.value for status in AllergyCommand.Severity])
        return {
            "keywords": "comma separated keywords of up to 5 distinct synonyms of the component related to the allergy or 'NKA' for No Known Allergy or 'NKDA' for No Known Drug Allergy",
            "type": "mandatory, one of: allergy group/medication/ingredient",
            "severity": f"mandatory, one of: {severity}",
            "reaction": "description of the reaction, as free text",
            "approximateDateOfOnset": "YYYY-MM-DD",
        }

    def instruction_description(self) -> str:
        return ("Any diagnosed allergy, one instruction per allergy. "
                "There can be only one allergy per instruction, and no instruction in the lack of. "
                "But, if it is explicitly said that the patient has no known allergy, add an instruction mentioning it.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([allergy.label for allergy in self.cache.current_allergies()]):
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
