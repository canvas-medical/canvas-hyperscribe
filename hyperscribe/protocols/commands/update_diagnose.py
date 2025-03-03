import json

from canvas_sdk.commands.commands.update_diagnosis import UpdateDiagnosisCommand

from hyperscribe.protocols.canvas_science import CanvasScience
from hyperscribe.protocols.commands.base import Base
from hyperscribe.protocols.constants import Constants
from hyperscribe.protocols.helper import Helper
from hyperscribe.protocols.structures.coded_item import CodedItem


class UpdateDiagnose(Base):
    @classmethod
    def schema_key(cls) -> str:
        return Constants.SCHEMA_KEY_UPDATE_DIAGNOSE

    @classmethod
    def staged_command_extract(cls, data: dict) -> None | CodedItem:
        if condition := (data.get("condition") or {}).get("text"):
            new_condition = (data.get("new_condition") or {}).get("text") or "n/a"
            narrative = data.get("narrative") or "n/a"
            return CodedItem(label=f"{condition} to {new_condition}: {narrative}", code="", uuid="")
        return None

    def command_from_json(self, parameters: dict) -> None | UpdateDiagnosisCommand:
        result = UpdateDiagnosisCommand(
            background=parameters["rationale"],
            narrative=parameters["assessment"],
            note_uuid=self.note_uuid,
        )
        if 0 <= (idx := parameters["previousConditionIndex"]) < len(current := self.cache.current_conditions()):
            result.condition_code = current[idx].code

        # retrieve existing conditions defined in Canvas Science
        expressions = parameters["keywords"].split(",") + parameters["ICD10"].split(",")
        if conditions := CanvasScience.search_conditions(self.settings.science_host, expressions):
            # retrieve the correct condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition diagnosed for a patient out of a list of conditions.",
                "",
            ]
            user_prompt = [
                'Here is the comment provided by the healthcare provider in regards to the diagnosis:',
                '```text',
                f"keywords: {parameters['keywords']}",
                " -- ",
                parameters["rationale"],
                "",
                parameters["assessment"],
                '```',
                "",
                'Among the following conditions, identify the most relevant one:',
                '',
                "\n".join(f' * {condition.label} (ICD-10: {Helper.icd10_add_dot(condition.code)})' for condition in conditions),
                '',
                'Please, present your findings in a JSON format within a Markdown code block like:',
                '```json',
                json.dumps([{"ICD10": "the ICD-10 code", "description": "the description"}]),
                '```',
                '',
            ]
            if response := Helper.chatter(self.settings).single_conversation(system_prompt, user_prompt):
                result.new_condition_code = Helper.icd10_strip_dot(response[0]["ICD10"])
        return result

    def command_parameters(self) -> dict:
        conditions = "/".join([f'{condition.label} (index: {idx})' for idx, condition in enumerate(self.cache.current_conditions())])
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the new diagnosed condition",
            "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the new diagnosed condition",
            "previousCondition": f"one of: {conditions}",
            "previousConditionIndex": "index of the previous Condition, as integer",
            "rationale": "rationale about the current assessment, as free text",
            "assessment": "today's assessment of the new condition, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f'{condition.label}' for condition in self.cache.current_conditions()])
        return (f"Change of a medical condition ({text}) identified by the provider, including rationale, current assessment. "
                "There is one instruction per condition change, and no instruction in the lack of.")

    def instruction_constraints(self) -> str:
        text = ", ".join([f'{condition.label} (ICD-10: {condition.code})' for condition in self.cache.current_conditions()])
        return f"'{self.class_name()}' has to be an update from one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_conditions())
