import json

from canvas_sdk.commands.commands.update_diagnosis import UpdateDiagnosisCommand

from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


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

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        result = UpdateDiagnosisCommand(
            background=instruction.parameters["rationale"],
            narrative=instruction.parameters["assessment"],
            note_uuid=self.identification.note_uuid,
        )
        if (
            0
            <= (idx := instruction.parameters["previousConditionIndex"])
            < len(current := self.cache.current_conditions())
        ):
            result.condition_code = current[idx].code

        # retrieve existing conditions defined in Canvas Science
        expressions = instruction.parameters["keywords"].split(",") + instruction.parameters["ICD10"].split(",")
        if conditions := CanvasScience.search_conditions(self.settings.science_host, expressions):
            # retrieve the correct condition
            system_prompt = [
                "The conversation is in the medical context.",
                "",
                "Your task is to identify the most relevant condition diagnosed for a patient "
                "out of a list of conditions.",
                "",
            ]
            user_prompt = [
                "Here is the comment provided by the healthcare provider in regards to the diagnosis:",
                "```text",
                f"keywords: {instruction.parameters['keywords']}",
                " -- ",
                instruction.parameters["rationale"],
                "",
                instruction.parameters["assessment"],
                "```",
                "",
                "Among the following conditions, identify the most relevant one:",
                "",
                "\n".join(
                    f" * {condition.label} (ICD-10: {Helper.icd10_add_dot(condition.code)})" for condition in conditions
                ),
                "",
                "Please, present your findings in a JSON format within a Markdown code block like:",
                "```json",
                json.dumps([{"ICD10": "the ICD-10 code", "description": "the description"}]),
                "```",
                "",
            ]
            schemas = JsonSchema.get(["selector_condition"])
            if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
                result.new_condition_code = Helper.icd10_strip_dot(response[0]["ICD10"])
        return InstructionWithCommand.add_command(instruction, result)

    def command_parameters(self) -> dict:
        conditions = "/".join(
            [f"{condition.label} (index: {idx})" for idx, condition in enumerate(self.cache.current_conditions())],
        )
        return {
            "keywords": "comma separated keywords of up to 5 synonyms of the new diagnosed condition",
            "ICD10": "comma separated keywords of up to 5 ICD-10 codes of the new diagnosed condition",
            "previousCondition": f"one of: {conditions}",
            "previousConditionIndex": "index of the previous Condition, or -1, as integer",
            "rationale": "rationale about the current assessment, as free text",
            "assessment": "today's assessment of the new condition, as free text",
        }

    def instruction_description(self) -> str:
        text = ", ".join([f"{condition.label}" for condition in self.cache.current_conditions()])
        return (
            f"Change of a medical condition ({text}) identified by the provider, "
            f"including rationale, current assessment. "
            "There is one instruction per condition change, and no instruction in the lack of."
        )

    def instruction_constraints(self) -> str:
        text = ", ".join(
            [f"{condition.label} (ICD-10: {condition.code})" for condition in self.cache.current_conditions()],
        )
        return f"'{self.class_name()}' has to be an update from one of the following conditions: {text}"

    def is_available(self) -> bool:
        return bool(self.cache.current_conditions())
