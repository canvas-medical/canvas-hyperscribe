from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class SurgeryHistory(Base):
    def command_from_json(self, parameters: dict) -> None | PastSurgicalHistoryCommand:
        # retrieve existing family history conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        concepts = CanvasScience.surgical_histories(self.settings.science_host, expressions)

        # ask the LLM to pick the most relevant condition
        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant surgery of a patient out of a list of surgeries.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the surgery of a patient:',
            '```text',
            parameters["comment"],
            '```',
            'Among the following surgeries, identify the most relevant one:',
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
        surgery = ""
        if response.has_error is False and response.content:
            surgery = response.content[0]["term"]

        return PastSurgicalHistoryCommand(
            past_surgical_history=surgery,
            approximate_date=self.str2date(parameters["approximateDate"]).date(),
            comment=parameters["comment"],
            note_uuid=self.note_uuid,
        )

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the surgery",
            "approximateDate": "YYYY-MM-DD",
            "comment": "free text describing the surgery",
        }

    def instruction_description(self) -> str:
        return ("Any past surgery. "
                "There can be only one surgery per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
