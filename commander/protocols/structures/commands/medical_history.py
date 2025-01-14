from canvas_sdk.commands.commands.medical_history import MedicalHistoryCommand
from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class MedicalHistory(Base):
    def from_json(self, parameters: dict) -> None | PastSurgicalHistoryCommand:
        # retrieve existing medical history conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        concepts = CanvasScience.medical_histories(self.settings.science_host, expressions)

        # ask the LLM to pick the most relevant condition
        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the condition of a patient:',
            '```text',
            parameters["comments"],
            '```',
            'Among the following conditions, identify the most relevant one:',
            '',
            "\n".join(f' * {concept.label} (ICD10: {concept.code})' for concept in concepts),
            '',
            'Please present your findings in a JSON format within a Markdown code block like',
            '```json',
            '[{"icd10": "the concept ID", "label": "the expression"]'
            '```',
            '',
        ]
        response = conversation.chat()
        condition = ""
        if response.has_error is False and response.content:
            condition = response.content[0]["label"]

        return MedicalHistoryCommand(
            past_medical_history=condition,
            approximate_start_date=self.str2date(parameters["approximateStartDate"]).date(),
            approximate_end_date=self.str2date(parameters["approximateEndDate"]).date(),
            show_on_condition_list=True,
            comments=parameters["comments"],
            note_uuid=self.note_uuid,
        )

    def parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the condition",
            "approximateStartDate": "YYYY-MM-DD",
            "approximateEndDate": "YYYY-MM-DD",
            "comments": "free text describing the condition in less than 900 characters",
        }

    def information(self) -> str:
        return ("Any past condition. "
                "There can be only one condition per instruction, and no instruction in the lack of.")

    def constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
