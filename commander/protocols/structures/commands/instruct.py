import json

from canvas_sdk.commands.commands.instruct import InstructCommand
from logger import log

from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class Instruct(Base):
    def from_json(self, parameters: dict) -> None | InstructCommand:
        # TODO retrieve the list of the instructions (https://science-staging.canvasmedical.com/search/instruction?query=xxxx&limit=10)
        #  for each keyword and submit them to the LLM to pick the most relevant
        #  the host science-staging.canvasmedical.com can be provided through the secrets
        science_instructions = [
            {
                "concept_id": 170961007,
                "term": "Menopause: dietary advice",
                "score": 0,
                "frequencies": {
                    "query:snomed": 0,
                    ":snomed": 0
                }
            },
            {
                "concept_id": 171054004,
                "term": "Dietary advice for pregnancy",
                "score": 0,
                "frequencies": {
                    "query:snomed": 0,
                    ":snomed": 0
                }
            },
            {
                "concept_id": 183057009,
                "term": "Patient advised about gluten-free diet",
                "score": 0,
                "frequencies": {
                    "query:snomed": 0,
                    ":snomed": 0
                }
            },
            {
                "concept_id": 183058004,
                "term": "Patient advised about phenylalanine-free diet",
                "score": 0,
                "frequencies": {
                    "query:snomed": 0,
                    ":snomed": 0
                }
            },
        ]

        model = "gpt-4o"
        temperature = 0.0
        conversation = OpenaiChat(self.openai_key, model, temperature)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant direction.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the description of a direction instructed by a healthcare provider to a patient:',
            '```text',
            parameters["comment"],
            '```',
            'Among the following expressions, identify the most relevant one:',
            '',
            "\n".join(f' * {concept["term"]} ({concept["concept_id"]})' for concept in science_instructions),
            '',
            'Please present your findings in a JSON format within a Markdown code block like',
            '```json',
            '[{"concept_id": "the concept ID", "term": "the expression"]'
            '```',
            '',
        ]
        response = conversation.chat()
        instruction = "Advice to read information"
        if response.has_error is False and response.content:
            instruction = response.content[0]["term"]

        return InstructCommand(
            instruction=instruction,
            comment=parameters["comment"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "keywords": "comma separated single keywords of up to 5 synonyms to the specific direction",
            "comment": "direction as free text",
        }

    def information(self) -> str:
        return ("Specific or standard direction. "
                "There can be only one direction per instruction, and no instruction in the lack of.")

    def is_available(self) -> bool:
        return True
