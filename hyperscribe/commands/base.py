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
            "Medical context: create clinical charting shorthand summary (SOAP style) from JSON.",
            "JSON contains: command (detailed values), previousInformation (current), information (updated).",
            "",
            "Use medical abbreviations (CC, f/u, Dx, Rx, DC, VS, FHx, labs).",
            "Telegraphic, concise, for quick glance by knowledgeable person. Only new information. Max 20 words.",
        ]
        user_prompt = [
            "JSON:",
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
            "Return summary as JSON in Markdown code block:",
            "```json",
            json.dumps([{"summary": "shorthand summary"}]),
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
            f"Clinical encounter context: patient ({self.cache.demographic__str__(False)}) and provider.",
            f"Current time: {datetime.now().isoformat()}",
            "",
            "Apply requested changes to data. Follow instructions exactly.",
            "IMPORTANT: Never add information not in original data. "
            "Better to keep unchanged than create incorrect information.",
        ]
        user_prompt = [
            "Original data:",
            "```text",
            data,
            "```",
            "",
            "Changes to apply:",
            "```text",
            prompt,
            "```",
            "",
            "Return modified data as JSON in Markdown code block:",
            "```json",
            json.dumps([{"newData": "modified data"}]),
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
