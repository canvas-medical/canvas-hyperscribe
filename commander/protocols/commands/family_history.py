import json

from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.openai_chat import OpenaiChat


class FamilyHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return "familyHistory"

    def command_from_json(self, parameters: dict) -> None | FamilyHistoryCommand:
        result = FamilyHistoryCommand(
            relative=parameters["relative"],
            note=parameters["note"],
            note_uuid=self.note_uuid,
        )
        # retrieve existing family history conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        if concepts := CanvasScience.family_histories(self.settings.science_host, expressions):
            # ask the LLM to pick the most relevant condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
                "",
            ]
            user_prompt = [
                'Here is the note provided by the healthcare provider in regards to the condition of a patient:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                parameters["note"],
                '```',
                'Among the following conditions, identify the most relevant one:',
                '',
                "\n".join(f' * {concept.term} ({concept.concept_id})' for concept in concepts),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"concept_id": "the concept ID", "term": "the expression"}]),
                '```',
                '',
            ]
            if response := OpenaiChat.single_conversation(self.settings.openai_key, system_prompt, user_prompt):
                result.family_history = response[0]["term"]
        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the condition",
            "relative": "one of: father/mother/parent/child/brother/sister/sibling/grand-parent/grand-father/grand-mother",
            "note": "description of the condition, as free text",
        }

    def instruction_description(self) -> str:
        return ("Any relevant condition of a relative among: "
                "father, mother, parent, child, brother, sister, sibling, grand-parent, grand-father, grand-mother. "
                "There can be only one condition per relative per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'{history.label}' for history in self.family_history()]):
            result = f'"{self.class_name()}" cannot include: {text}.'
        return result

    def is_available(self) -> bool:
        return True
