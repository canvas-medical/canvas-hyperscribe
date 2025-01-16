from canvas_sdk.commands.commands.instruct import InstructCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class Instruct(Base):
    def command_from_json(self, parameters: dict) -> None | InstructCommand:
        # retrieve existing instructions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        concepts = CanvasScience.instructions(self.settings.science_host, expressions)

        # ask the LLM to pick the most relevant instruction
        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
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
            "\n".join(f' * {concept.term} ({concept.concept_id})' for concept in concepts),
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

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated single keywords of up to 5 synonyms to the specific direction",
            "comment": "directions from the provider, as free text",
        }

    def instruction_description(self) -> str:
        return ("Specific or standard direction. "
                "There can be only one direction per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
