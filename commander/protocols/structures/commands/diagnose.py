from canvas_sdk.commands.commands.diagnose import DiagnoseCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.commands.base import Base


class Diagnose(Base):
    def command_from_json(self, parameters: dict) -> None | DiagnoseCommand:
        # retrieve existing conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",") + parameters["ICD10"].split(",")
        conditions = CanvasScience.search_conditions(self.settings.science_host, expressions)

        conversation = OpenaiChat(self.settings.openai_key, Constants.OPENAI_CHAT_TEXT)
        # retrieve the correct condition
        conversation.system_prompt = [
            "The conversation is in the medical context.",
            "",
            "Your task is to identify the most relevant condition diagnosed for a patient out of a list of conditions.",
            "",
        ]
        conversation.user_prompt = [
            'Here is the comment provided by the healthcare provider in regards to the diagnosis:',
            '```text',
            parameters["background"],
            "",
            parameters["assessment"],
            '```',
            "",
            'Among the following conditions, identify the most relevant one:',
            '',
            "\n".join(f' * {condition.label} (ICD-10: {self.icd10_add_dot(condition.code)})' for condition in conditions),
            '',
            'Please present your findings in a JSON format within a Markdown code block like',
            '```json',
            '[{"ICD10": "the ICD-10 code", "description": "the description"]'
            '```',
            '',
        ]
        response = conversation.chat()
        result = DiagnoseCommand(
            background=parameters["background"],
            approximate_date_of_onset=self.str2date(parameters["onsetDate"]).date(),
            today_assessment=parameters["assessment"],
            note_uuid=self.note_uuid,
        )
        if response.has_error is False and response.content:
            icd10 = self.icd10_strip_dot(response.content[0]["ICD10"])
            result.icd10_code = icd10
        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the diagnosed condition",
            "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the diagnosed condition",
            "background": "free text",
            "onsetDate": "YYYY-MM-DD",
            "assessment": "free text",
        }

    def instruction_description(self) -> str:
        return ("Medical condition identified by the provider, including reasoning, current assessment, and onset date. "
                "There is one instruction per condition, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        return ""

    def is_available(self) -> bool:
        return True
