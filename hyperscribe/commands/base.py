import json
import re
from datetime import datetime

from logger import log

from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.template_permissions import TemplatePermissions
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
        self.permissions = TemplatePermissions(identification.note_uuid)

    @classmethod
    def class_name(cls) -> str:
        return cls.__name__

    @classmethod
    def command_type(cls) -> str:
        raise NotImplementedError

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

    # -- Template integration ------------------------------------------------

    def can_edit_command(self) -> bool:
        """Check if this command type is editable based on template permissions."""
        command_type = self.command_type()
        permissions = self.permissions.load_permissions()
        if command_type not in permissions:
            return True
        return bool(permissions[command_type].get("plugin_can_edit", True))

    def can_edit_field(self, field_name: str) -> bool:
        """Check if a field can be edited based on template permissions."""
        command_type = self.command_type()
        permissions = self.permissions.load_permissions()
        if command_type not in permissions:
            return True

        cmd_perms = permissions[command_type]
        if not cmd_perms.get("plugin_can_edit", True):
            return False

        for fp in cmd_perms.get("field_permissions", []):
            if fp.get("field_name") == field_name:
                return bool(fp.get("plugin_can_edit", True))

        return True

    def get_template_instructions(self, field_name: str) -> list[str]:
        """Get {add:} instructions from template for a specific field."""
        command_type = self.command_type()
        permissions = self.permissions.load_permissions()
        if command_type not in permissions:
            return []

        for fp in permissions[command_type].get("field_permissions", []):
            if fp.get("field_name") == field_name:
                instructions = fp.get("add_instructions", [])
                return list(instructions) if instructions else []

        return []

    def get_template_framework(self, field_name: str) -> str | None:
        """Get the template framework (base content) for a field."""
        command_type = self.command_type()
        permissions = self.permissions.load_permissions()
        if command_type not in permissions:
            return None

        for fp in permissions[command_type].get("field_permissions", []):
            if fp.get("field_name") == field_name:
                framework = fp.get("plugin_edit_framework")
                return str(framework) if framework else None

        return None

    def _resolve_framework(self, field_name: str) -> str | None:
        """Resolve template framework from cache."""
        framework = self.get_template_framework(field_name)
        if framework:
            log.info(
                f"[TEMPLATE] Resolved cached framework for {self.class_name()}.{field_name} (length={len(framework)})"
            )
            return framework
        log.info(f"[TEMPLATE] No framework resolved for {self.class_name()}.{field_name}")
        return None

    def resolve_field(
        self,
        field_name: str,
        param_value: str,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> str | None:
        """Check edit permission and fill template content. Returns None if locked."""
        if not self.can_edit_field(field_name):
            return None
        return self.fill_template_content(param_value, field_name, instruction, chatter)

    def fill_template_content(
        self,
        generated_content: str,
        field_name: str,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> str:
        """Merge generated content with template framework, or return as-is if no template."""
        log.info(f"[TEMPLATE] fill_template_content: {self.class_name()}.{field_name}")

        framework = self._resolve_framework(field_name)
        add_instructions = self.get_template_instructions(field_name)

        if not framework and not add_instructions:
            return generated_content

        if not framework:
            log.info(f"[TEMPLATE] No framework, enhancing with add_instructions: {add_instructions}")
            return self.enhance_with_template_instructions(generated_content, add_instructions, instruction, chatter)

        # Strip {lit:} markers from framework — they declare protected text
        # in the cache but should not appear in the LLM prompt.
        display_framework = re.sub(r"\{lit:([^}]*)\}", r"\1", framework)

        schemas = JsonSchema.get(["template_enhanced_content"])
        system_prompt = [
            "The conversation is in the context of a clinical encounter between "
            f"patient ({self.cache.demographic__str__(False)}) and licensed healthcare provider.",
            "",
            "You are updating a medical note that has a specific structure with section headers.",
            "Your task is to preserve this EXACT structure while updating the content.",
            "",
            "CRITICAL REQUIREMENTS:",
            "- Keep ALL existing text from the original content - do NOT delete any lines",
            "- Keep ALL section headers exactly as they appear",
            "- Keep the same line breaks and paragraph structure",
            "- Only ADD information from the transcript to fill in empty sections",
            "- Do NOT convert the structured format into prose paragraphs",
            "- Do NOT remove, delete, or merge any existing content",
            "- Do not fabricate or invent clinical details",
            "- If a section is already filled, keep it as-is unless the transcript has updates",
            "",
            f"Current date/time: {datetime.now().isoformat()}",
            "",
        ]

        add_instruction_text = ""
        if add_instructions:
            add_instruction_text = f"\n\nThe template expects information about: {', '.join(add_instructions)}"

        user_prompt = [
            "EXISTING STRUCTURED CONTENT (preserve this exact format):",
            "```text",
            display_framework,
            "```",
            "",
            "UPDATED INFORMATION from the transcript:",
            "```text",
            generated_content,
            "```",
            add_instruction_text,
            "",
            "IMPORTANT: Keep ALL existing text from the original. Do NOT delete any lines.",
            "Only fill in empty sections with information from the transcript.",
            "Return the content with the EXACT same text, headers, and layout as the original.",
            "",
            "Your response must be a JSON Markdown block:",
            "```json",
            json.dumps([{"enhancedContent": "the structured content with same format as original"}]),
            "```",
            "",
        ]

        chatter.reset_prompts()
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            if filled := str(response[0].get("enhancedContent")):
                return filled

        # Fallback to generated content if template filling fails
        return generated_content

    def enhance_with_template_instructions(
        self,
        content: str,
        add_instructions: list[str],
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> str:
        """Enhance content based on template {add:} instructions using the LLM."""
        schemas = JsonSchema.get(["template_enhanced_content"])
        system_prompt = [
            "The conversation is in the context of a clinical encounter between "
            f"patient ({self.cache.demographic__str__(False)}) and licensed healthcare provider.",
            "",
            "You are enhancing a medical note field based on template guidance.",
            "The user will provide the current content and specific topics that should be included.",
            "Your task is to incorporate the requested information naturally into the narrative.",
            "",
            "Important guidelines:",
            "- Only add information that can be supported by the transcript",
            "- Do not fabricate or invent clinical details",
            "- Maintain the existing style and tone of the content",
            "- If the requested information is not present in the transcript, do not add it",
            "",
            f"Current date/time: {datetime.now().isoformat()}",
            "",
        ]
        user_prompt = [
            "Current content:",
            "```text",
            content,
            "```",
            "",
            "Original transcript information:",
            "```text",
            instruction.information,
            "```",
            "",
            f"Please ensure the content includes information about: {', '.join(add_instructions)}",
            "",
            "Return the enhanced content. If the requested information is not available "
            "in the transcript, return the original content unchanged.",
            "",
            "Your response must be a JSON Markdown block:",
            "```json",
            json.dumps([{"enhancedContent": "the enhanced content here"}]),
            "```",
            "",
        ]

        chatter.reset_prompts()
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            if enhanced := str(response[0].get("enhancedContent")):
                return enhanced

        return content
