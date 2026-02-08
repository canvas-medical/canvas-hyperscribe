"""Template integration mixin for Base command class.

Extracts template permission checking, framework resolution, and content
filling into a separate mixin to keep base.py focused on command protocol.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from logger import log

from hyperscribe.libraries.json_schema import JsonSchema
from hyperscribe.libraries.template_constants import get_schema_key
from hyperscribe.libraries.template_permissions import TemplatePermissions
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


class TemplateIntegrationMixin:
    """Mixin providing template permission and content filling for commands.

    Expects the consuming class (Base) to provide:
        _template_permissions, identification, cache, class_name()
    """

    # Declare types for attributes provided by Base so mypy can check this file.
    _template_permissions: TemplatePermissions | None
    identification: "Any"
    cache: "Any"

    @classmethod
    def class_name(cls) -> str:
        raise NotImplementedError

    @property
    def template_permissions(self) -> TemplatePermissions:
        """Lazily initialize and return the TemplatePermissions instance."""
        if self._template_permissions is None:
            self._template_permissions = TemplatePermissions(self.identification.note_uuid)
        return self._template_permissions

    def can_edit_field(self, field_name: str) -> bool:
        """Check if a field can be edited based on template permissions."""
        return self.template_permissions.can_edit_field(self.class_name(), field_name)

    def get_template_instructions(self, field_name: str) -> list[str]:
        """Get {add:} instructions from template for a specific field."""
        return self.template_permissions.get_add_instructions(self.class_name(), field_name)

    def get_template_framework(self, field_name: str) -> str | None:
        """Get the template framework (base content) for a field."""
        return self.template_permissions.get_edit_framework(self.class_name(), field_name)

    def get_current_note_content(self, field_name: str) -> str | None:
        """Read the current content from the note for this command type and field."""
        try:
            from canvas_sdk.v1.data.note import Note

            schema_key = get_schema_key(self.class_name())
            if not schema_key:
                log.info(f"[TEMPLATE] No schema_key mapping for {self.class_name()}")
                return None

            note = Note.objects.get(id=self.identification.note_uuid)
            commands = note.commands.filter(schema_key=schema_key)

            for command in commands:
                if command.data and field_name in command.data:
                    content = command.data.get(field_name)
                    if content:
                        log.info(f"[TEMPLATE] Found existing {schema_key}.{field_name} content (length={len(content)})")
                        return str(content)

            log.info(f"[TEMPLATE] No existing {schema_key}.{field_name} content found in note")
            return None

        except Exception as e:
            log.warning(f"[TEMPLATE] Error reading note content: {e}")
            return None

    def _resolve_framework(self, field_name: str) -> str | None:
        """Resolve template framework from cache or existing note content."""
        framework = self.get_template_framework(field_name)
        if framework:
            log.info(
                f"[TEMPLATE] Resolved cached framework for {self.class_name()}.{field_name} (length={len(framework)})"
            )
            return framework

        existing_content = self.get_current_note_content(field_name)
        if existing_content:
            has_structure = self._has_structured_content(existing_content)
            if has_structure:
                log.info(
                    f"[TEMPLATE] Using note content as framework for "
                    f"{self.class_name()}.{field_name} (length={len(existing_content)})"
                )
                return existing_content
            else:
                log.info(f"[TEMPLATE] Note content for {self.class_name()}.{field_name} has no structure, skipping")

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

        if not framework:
            if add_instructions:
                log.info(f"[TEMPLATE] No framework, enhancing with add_instructions: {add_instructions}")
            return self.enhance_with_template_instructions(generated_content, field_name, instruction, chatter)

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
            filled = str(response[0].get("enhancedContent", generated_content))
            if filled:
                return filled

        # Fallback to generated content if template filling fails
        return generated_content

    def _has_structured_content(self, content: str) -> bool:
        """Check if content has structure worth preserving (2+ section headers)."""
        if not content or len(content) < 50:
            return False

        lines = content.strip().split("\n")

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

        return header_pattern_count >= 2

    def enhance_with_template_instructions(
        self,
        content: str,
        field_name: str,
        instruction: InstructionWithParameters,
        chatter: LlmBase,
    ) -> str:
        """Enhance content based on template {add:} instructions using the LLM."""
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
