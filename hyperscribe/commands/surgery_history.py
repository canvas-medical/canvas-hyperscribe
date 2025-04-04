import json

from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.commands.base import Base
from hyperscribe.handlers.constants import Constants
from hyperscribe.handlers.helper import Helper
from hyperscribe.handlers.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem


class SurgeryHistory(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_SURGERY_HISTORY

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        comment = data.get("comment") or "n/a"
        on_date = (data.get("approximate_date") or {}).get("date") or "n/a"
        if surgery := (data.get("past_surgical_history") or {}).get("text"):
            code = str((data.get('past_surgical_history') or {}).get("value") or "")
            return CodedItem(label=f"{surgery}: {comment} (on: {on_date})", code=code, uuid="")
        return None

    def command_from_json(self, chatter: LlmBase, parameters: dict) -> None | PastSurgicalHistoryCommand:
        result = PastSurgicalHistoryCommand(
            approximate_date=Helper.str2date(parameters["approximateDate"]),
            comment=parameters["comment"],
            note_uuid=self.note_uuid,
        )
        # retrieve existing family history conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",")
        if concepts := CanvasScience.surgical_histories(self.settings.science_host, expressions):
            # ask the LLM to pick the most relevant condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant surgery of a patient out of a list of surgeries.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the surgery of a patient:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                parameters["comment"],
                '```',
                'Among the following surgeries, identify the most relevant one:',
                '',
                "\n".join(f' * {concept.term} ({concept.concept_id})' for concept in concepts),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"conceptId": "the concept ID", "term": "the expression"}]),
                '```',
                '',
            ]
            schemas = JsonSchema.get(["selector_concept"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas):
                result.past_surgical_history = response[0]["term"]

        return result

    def command_parameters(self) -> dict:
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the surgery",
            "approximateDate": "YYYY-MM-DD",
            "comment": "description of the surgery, as free text",
        }

    def instruction_description(self) -> str:
        return ("Any past surgery. "
                "There can be only one surgery per instruction, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        result = ""
        if text := ", ".join([f'"{surgery.label}"' for surgery in self.cache.surgery_history()]):
            result = f'"{self.class_name()}" cannot include: {text}.'
        return result

    def is_available(self) -> bool:
        return True
