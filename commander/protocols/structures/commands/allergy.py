import json

from canvas_sdk.commands.commands.allergy import AllergyCommand, Allergen, AllergenType

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class Allergy(Base):
    def command_from_json(self, parameters: dict) -> None | AllergyCommand:
        concept_type = AllergenType(1)
        if parameters["type"] == "medication":
            concept_type = AllergenType(2)
        elif parameters["type"] == "ingredient":
            concept_type = AllergenType(6)

        # retrieve existing allergies defined in Canvas Ontologies
        expressions = parameters["keywords"].split(",")
        allergies = CanvasScience.search_allergy(
            self.settings.ontologies_host,
            self.settings.pre_shared_key,
            expressions,
            [AllergenType(1), concept_type],  # <-- always include the Allergy Group
        )

        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        # retrieve the correct allergy
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant allergy of a patient out of a list of allergies.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the allergy:',
            '```text',
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
        response = conversation.chat()
        result = AllergyCommand(
            severity=self.enum_or_none(parameters["severity"], AllergyCommand.Severity),
            narrative=parameters["reaction"],
            approximate_date=self.str2date(parameters["approximateDateOfOnset"]),
            note_uuid=self.note_uuid,
        )

        if response.has_error is False and response.content:
            concept_id = int(response.content[0]["conceptId"])
            result.allergy = Allergen(
                concept_id=concept_id,
                concept_type=concept_type,
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
                "But, if it is explicitly said that the patient has no know allergy, add an instruction mentioning it.")

    def instruction_constraints(self) -> str:
        result = ""
        if self.current_allergies():
            text = ", ".join([allergy.label for allergy in self.current_allergies()])
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
