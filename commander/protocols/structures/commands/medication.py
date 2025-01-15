from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class Medication(Base):
    def from_json(self, parameters: dict) -> None | MedicationStatementCommand:
        # retrieve existing medications defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        medications = CanvasScience.medication_details(self.settings.science_host, expressions)

        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        # retrieve the correct medication
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the prescription:',
            '```text',
            parameters["sig"],
            '```',
            "",
            'Among the following medications, identify the most relevant one:',
            '',
            "\n".join(f' * {medication.description} (fdbCode: {medication.fdb_code})' for medication in medications),
            '',
            'Please present your findings in a JSON format within a Markdown code block like',
            '```json',
            '[{"fdbCode": "the fdb code, as int", "description": "the description"]'
            '```',
            '',
        ]
        response = conversation.chat()
        result = MedicationStatementCommand(
            sig=parameters["sig"],
            note_uuid=self.note_uuid,
        )
        if response.has_error is False and response.content:
            fdb_code = str(response.content[0]["fdbCode"])
            result.fdb_code = fdb_code
        return result

    def parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the taken medication",
            "sig": "directions, as free text",
        }

    def information(self) -> str:
        return ("Current medication. "
                "There can be only one medication per instruction, and no instruction in the lack of.")

    def constraints(self) -> str:
        if self.current_medications():
            text = ", ".join([medication.label for medication in self.current_medications()])
            return f"'{self.class_name()}' cannot include: {text}."
        return ""

    def is_available(self) -> bool:
        return True
