import json

from canvas_sdk.commands.commands.medical_history import MedicalHistoryCommand

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.json_schema import JsonSchema
from hyperscribe.handlers.structures.coded_item import CodedItem


class MedicalHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_MEDICAL_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comments") or "n/a"
        start_date = (data.get("approximate_start_date") or {}).get("date") or "n/a"
        end_date = (data.get("approximate_end_date") or {}).get("date") or "n/a"
        if text := (data.get("past_medical_history") or {}).get("text"):
            return CodedItem(label=f"{text}: from {start_date} to {end_date} ({comment})", code="", uuid="")
        return None

    def command_from_json(self, parameters: dict) -> None | MedicalHistoryCommand:
        result = MedicalHistoryCommand(
            approximate_start_date=Helper.str2date(parameters["approximateStartDate"]),
            approximate_end_date=Helper.str2date(parameters["approximateEndDate"]),
            show_on_condition_list=True,
            comments=parameters["comments"],
            note_uuid=self.note_uuid,
        )
        # retrieve existing medical history conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        if concepts := CanvasScience.medical_histories(self.settings.science_host, expressions):
            # ask the LLM to pick the most relevant condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the condition of a patient:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                parameters["comments"],
                '```',
                'Among the following conditions, identify the most relevant one:',
                '',
                "\n".join(f' * {concept.label} (ICD10: {concept.code})' for concept in concepts),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"ICD10": "the ICD-10 code", "label": "the label"}]),
                '```',
                '',
            ]
            schemas = JsonSchema.get(["selector_condition"])
            if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt, schemas):
                result.past_medical_history = response[0]["label"]
        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the condition",
            "approximateStartDate": "YYYY-MM-DD",
            "approximateEndDate": "YYYY-MM-DD",
            "comments": "provided description of the patient specific history with the condition, as free text",
        }

    def instruction_description(self) -> str:
        return ("Any past condition. "
                "There can be only one condition per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'{condition.label}' for condition in self.cache.condition_history()]):
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
