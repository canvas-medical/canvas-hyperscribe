import json
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
        self._template_permissions: TemplatePermissions | None = None

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

    # =========================================================================
    # Template Permission Methods
    # =========================================================================

    @property
    def template_permissions(self) -> TemplatePermissions:
        """Get the template permissions checker for this command's note.

        Lazily initializes the TemplatePermissions instance on first access.
        """
        if self._template_permissions is None:
            self._template_permissions = TemplatePermissions(self.identification.note_uuid)
        return self._template_permissions

    def can_edit_field(self, field_name: str) -> bool:
        """Check if a field can be edited based on template permissions.

        Args:
            field_name: The field name to check (e.g., "narrative", "background")

        Returns:
            True if the field can be edited, False if locked by template.
            Returns True if no template is applied.
        """
        return self.template_permissions.can_edit_field_by_class(self.class_name(), field_name)

    def get_template_instructions(self, field_name: str) -> list[str]:
        """Get {add:} instructions from template for a specific field.

        {add:} instructions tell the plugin what content should be included
        in the generated text for this field.

        Args:
            field_name: The field name to get instructions for

        Returns:
            List of instruction strings, or empty list if none.
        """
        return self.template_permissions.get_add_instructions_by_class(self.class_name(), field_name)

    def get_template_framework(self, field_name: str) -> str | None:
        """Get the template framework (base content) for a field.

        The framework is the template structure with {sub:} and {lit:} resolved,
        but with placeholders for {add:} content. This is used as the base
        when filling in template fields.

        Args:
            field_name: The field name to get the framework for

        Returns:
            The framework string, or None if no template is applied.
        """
        return self.template_permissions.get_edit_framework_by_class(self.class_name(), field_name)

    def fill_template_content(
        self,
        generated_content: str,
        field_name: str,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> str:
        """Fill template content by merging generated content with template framework.

        When a template is applied, this method uses the template framework as the base
        structure and incorporates the generated content into the {add:} placeholders.
        If no template is applied, returns the generated content as-is.

        Args:
            generated_content: The LLM-generated content to incorporate
            field_name: The field name being filled
            instruction: The instruction with parameters (contains transcript info)
            chatter: The LLM interface for merging content

        Returns:
            The filled template content, or generated content if no template.
        """
        # Debug: Log cache contents for template permissions
        log.info(f"[TEMPLATE DEBUG] ========== fill_template_content ==========")
        log.info(f"[TEMPLATE DEBUG] Command: {self.class_name()}, Field: {field_name}")
        log.info(f"[TEMPLATE DEBUG] Note UUID: {self.identification.note_uuid}")
        log.info(f"[TEMPLATE DEBUG] Has template applied: {self.template_permissions.has_template_applied()}")
        log.info(f"[TEMPLATE DEBUG] All cached permissions: {self.template_permissions._load_permissions()}")

        framework = self.get_template_framework(field_name)
        add_instructions = self.get_template_instructions(field_name)

        log.info(f"[TEMPLATE DEBUG] Framework from cache: {framework!r}")
        log.info(f"[TEMPLATE DEBUG] Add instructions: {add_instructions!r}")

        # If no framework from cache, check if existing content has structure worth preserving
        if not framework:
            existing_content = instruction.information
            has_structure = self._has_structured_content(existing_content)
            log.info(f"[TEMPLATE DEBUG] No framework from cache, checking existing content")
            log.info(f"[TEMPLATE DEBUG] Existing content (first 500 chars): {existing_content[:500]!r}")
            log.info(f"[TEMPLATE DEBUG] Has structure detected: {has_structure}")
            if has_structure:
                log.info(
                    f"[TEMPLATE] Using existing structured content as framework for {self.class_name()}.{field_name}"
                )
                framework = existing_content

        if not framework:
            # No template framework - use generated content with optional enhancement
            return self.enhance_with_template_instructions(generated_content, field_name, instruction, chatter)

        schemas = JsonSchema.get(["template_enhanced_content"])
        system_prompt = [
            "The conversation is in the context of a clinical encounter between "
            f"patient ({self.cache.demographic__str__(False)}) and licensed healthcare provider.",
            "",
            "You are updating a medical note that has a specific structure with section headers.",
            "Your task is to preserve this EXACT structure while updating the content.",
            "",
            "CRITICAL REQUIREMENTS:",
            "- Keep ALL section headers exactly as they appear (e.g., 'Current concerns with memory or cognition:')",
            "- Keep the same line breaks and paragraph structure",
            "- Only update the CONTENT within each section, not the headers themselves",
            "- Do NOT convert the structured format into prose paragraphs",
            "- Do NOT remove or merge sections",
            "- Do not fabricate or invent clinical details",
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
            framework,
            "```",
            "",
            "UPDATED INFORMATION from the transcript:",
            "```text",
            generated_content,
            "```",
            add_instruction_text,
            "",
            "Update the content while keeping the EXACT same structure, section headers, and formatting.",
            "Return the content with the same headers and layout as the original.",
            "",
            "Your response must be a JSON Markdown block:",
            "```json",
            json.dumps([{"enhancedContent": "the structured content with same format as original"}]),
            "```",
            "",
        ]

        chatter.reset_prompts()
        if response := chatter.single_conversation(system_prompt, user_prompt, schemas, instruction):
            filled = str(response[0].get("enhancedContent", generated_content))
            if filled:
                return filled

        # Fallback to generated content if template filling fails
        return generated_content

    def _has_structured_content(self, content: str) -> bool:
        """Check if content has structure worth preserving (section headers, etc.).

        Detects patterns like:
        - Lines ending with colons followed by content (section headers)
        - Known template section headers appearing inline
        - Multiple distinct sections separated by blank lines

        Args:
            content: The content to check

        Returns:
            True if the content appears to have intentional structure.
        """
        if not content or len(content) < 50:
            return False

        # Known template section header patterns (case-insensitive matching)
        # Include variations (e.g., "or" vs "and") that may appear in templates
        known_section_headers = [
            "current concerns with memory or cognition:",
            "current concerns with memory and cognition:",
            "current concerns with physical functioning:",
            "patient history provided by",  # No colon - may have content after
            "chief complaint:",
            "history of present illness:",
            "assessment:",
            "plan:",
        ]

        # First check for known template section headers anywhere in the content
        content_lower = content.lower()
        known_header_count = sum(1 for header in known_section_headers if header in content_lower)
        if known_header_count >= 2:
            return True

        # Fall back to line-by-line detection for other structured content
        lines = content.strip().split("\n")
        if len(lines) < 3:
            return False

        # Look for section header patterns (lines ending with colon, or "Header: content" patterns)
        header_pattern_count = 0
        for line in lines:
            line = line.strip()
            # Pattern: "Something something:" at start of line (section header)
            if line.endswith(":") and len(line) > 5:
                header_pattern_count += 1
            # Pattern: "Header: " followed by content on same line
            elif ": " in line and line.index(": ") < 60:
                prefix = line.split(": ")[0]
                # Check if prefix looks like a header (starts with capital, reasonable length)
                if prefix and prefix[0].isupper() and 3 <= len(prefix) <= 60:
                    header_pattern_count += 1

        # Consider structured if we find 2+ section headers
        return header_pattern_count >= 2

    def enhance_with_template_instructions(
        self,
        content: str,
        field_name: str,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> str:
        """Enhance content based on template {add:} instructions.

        If the template has {add:} instructions for this field, use the LLM
        to incorporate that information into the content based on the
        original transcript information.

        Args:
            content: The base content to enhance
            field_name: The field name being enhanced
            instruction: The instruction with parameters (contains transcript info)
            chatter: The LLM interface for generating enhanced content

        Returns:
            Enhanced content string, or original content if no instructions.
        """
        add_instructions = self.get_template_instructions(field_name)
        if not add_instructions:
            return content

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
            enhanced = str(response[0].get("enhancedContent", content))
            if enhanced:
                return enhanced

        return content
