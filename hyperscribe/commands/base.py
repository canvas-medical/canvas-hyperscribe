import json
from datetime import datetime

from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.instruction_with_summary import InstructionWithSummary
from hyperscribe.structures.settings import Settings


class Base:
    def __init__(self, settings: Settings, cache: LimitedCache, identification: IdentificationParameters):
        self.settings = settings
        self.identification = identification
        self.cache = cache
        self._arguments_code2description: dict[str, str] = {}

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    @classmethod
    def schema_key(cls) -> str:
        raise NotImplementedError

    @classmethod
    def note_section(cls) -> str:
        raise NotImplementedError

    @classmethod
    def staged_command_extract(cls, data: dict) -> CodedItem | None:
        raise NotImplementedError

    def custom_prompt(self) -> str:
        class_name = self.class_name()
        return next((cp.prompt for cp in self.settings.custom_prompts if cp.command == class_name and cp.active), "")

    def command_from_json(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithCommand | None:
        raise NotImplementedError

    def add_code2description(self, code: str, description: str) -> None:
        self._arguments_code2description[code] = description

    def command_from_json_with_summary(
        self,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> InstructionWithSummary | None:
        result = self.command_from_json(instruction, chatter)
        if result is None:
            return None

        attributes: dict = {}
        for key, value in result.command.values.items():
            if key in ("note_uuid", "command_uuid"):
                continue
            if isinstance(value, str) and value in self._arguments_code2description:
                value = self._arguments_code2description[value]
            if value:
                attributes[key] = value

        system_prompt = [
            "The conversation is in the medical context.",
            "The user will provide you with a JSON built for a medical software, including:",
            "- `command` providing accurate and detailed values",
            "- `previousInformation` a plain English description currently know by the software",
            "- `information` a plain English description built on top of `previousInformation`.",
            "",
            "Your task is to produce a summary in clinical charting shorthand style (like SOAP notes) "
            "out of this JSON.",
            "",
            "Use plain English with standard medical abbreviations (e.g., CC, f/u, Dx, Rx, DC, VS, FHx, labs).",
            "Be telegraphic, concise, and formatted like real chart notes for a quick glance from a knowledgeable "
            "person.",
            "Only new information should be included, and 20 words should be the maximum.",
        ]
        user_prompt = [
            "Here is a JSON intended to the medical software:",
            "```json",
            json.dumps(
                {
                    "previousInformation": result.previous_information,
                    "information": result.information,
                    "command": {
                        "name": result.command.__class__.__name__,
                        "attributes": attributes,
                    },
                }
            ),
            "```",
            "",
            "Please, following the directions, present the summary of the new information only like "
            "this Markdown code block:",
            "```json",
            json.dumps(
                [
                    {
                        "summary": "clinical charting shorthand style summary, minimal and "
                        "limited to the new information but useful for a quick glance from "
                        "a knowledgeable person"
                    }
                ]
            ),
            "```",
            "",
        ]

        schemas = JsonSchema.get(["command_summary"])
        summary = ""
        chatter.reset_prompts()
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            summary = str(response[0]["summary"])

        return InstructionWithSummary.add_explanation(
            instruction=result,
            summary=summary,
        )

    def command_from_json_custom_prompted(self, data: str, chatter: LlmBase) -> str:
        prompt = self.custom_prompt()
        if not prompt:
            return data

        schemas = JsonSchema.get(["command_custom_prompt"])
        system_prompt = [
            "The conversation is in the context of a clinical encounter between "
            f"patient ({self.cache.demographic__str__(False)}) and licensed healthcare provider.",
            "",
            "The user will submit to you some data related to the conversation as well as how to modify it.",
            "It is important to follow the requested changes without never make things up.",
            "It is better to keep the data unchanged rather than create incorrect information.",
            "",
            f"Please, note that now is {datetime.now().isoformat()}.",
            "",
        ]
        user_prompt = [
            "Here is the original data:",
            "```text",
            data,
            "```",
            "",
            "Apply the following changes:",
            "```text",
            prompt,
            "```",
            "",
            "Do NOT add information which is not explicitly provided in the original data.",
            "",
            "Fill the JSON object with the relevant information:",
            "```json",
            json.dumps([{"newData": ""}]),
            "```",
            "",
            "Your response must be a JSON Markdown block validated with the schema:",
            "```json",
            json.dumps(schemas[0], indent=1),
            "```",
            "",
        ]
        result = data
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, None):
            result = str(response[0]["newData"])
        return result

    def command_parameters(self) -> dict:
        raise NotImplementedError

    def command_parameters_schemas(self) -> list[dict]:
        return []

    def instruction_description(self) -> str:
        raise NotImplementedError

    def instruction_constraints(self) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError
