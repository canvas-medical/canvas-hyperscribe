import json

from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.json_schema import JsonSchema
from hyperscribe.handlers.structures.coded_item import CodedItem


class Medication(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_MEDICATION

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        sig = data.get("sig") or "n/a"
        if text := (data.get("medication") or {}).get("text"):
            return CodedItem(label=f"{text}: {sig}", code="", uuid="")
        return None

    def command_from_json(self, parameters: dict) -> None | MedicationStatementCommand:
        result = MedicationStatementCommand(
            sig=parameters["sig"],
            note_uuid=self.note_uuid,
        )
        # retrieve existing medications defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        if medications := CanvasScience.medication_details(self.settings.science_host, expressions):
            # retrieve the correct medication
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the prescription:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                parameters["sig"],
                '```',
                "",
                'Among the following medications, identify the most relevant one:',
                '',
                "\n".join(f' * {medication.description} (fdbCode: {medication.fdb_code})' for medication in medications),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"fdbCode": "the fdb code, as int", "description": "the description"}]),
                '```',
                '',
            ]
            schemas = JsonSchema.get(["selector_fdb_code"])
            if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt, schemas):
                result.fdb_code = str(response[0]["fdbCode"])
        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the taken medication",
            "sig": "directions, as free text",
        }

    def instruction_description(self) -> str:
        return ("Current medication. "
                "There can be only one medication per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([medication.label for medication in self.cache.current_medications()]):
            result = f"'{self.class_name()}' cannot include: {text}."
        return result

    def is_available(self) -> bool:
        return True
