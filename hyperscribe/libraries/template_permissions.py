"""Template permissions integration for note_templates plugin compatibility.

This module provides a service class that integrates with the note_templates plugin's
permission system, allowing Hyperscribe to respect template-defined edit restrictions
and incorporate {add:} instructions into content generation.
"""

from __future__ import annotations

from typing import Any, Callable

from logger import log

from hyperscribe.libraries.template_constants import (
    COMMAND_PERMISSIONS_KEY_PREFIX,
    get_command_type,
)

# Try to import get_cache at module level, with fallback for testing
try:
    from canvas_sdk.caching.plugins import get_cache as _get_cache
except ImportError:
    _get_cache = None


def _default_cache_getter() -> Any:
    """Default cache getter that uses the SDK's get_cache."""
    if _get_cache is None:
        raise ImportError("canvas_sdk.caching.plugins not available")
    return _get_cache()


class TemplatePermissions:
    """Integrates with note_templates plugin permission system.

    This class provides methods to check if commands and fields can be edited
    based on permissions stored by the note_templates plugin, and to retrieve
    {add:} instructions for content generation guidance.

    The note_templates plugin stores permissions in the Canvas SDK cache with the key:
        note_template_cmd_perms_{note_uuid}

    The structure is:
        {
            "CommandType": {
                "plugin_can_edit": bool,
                "field_permissions": [
                    {
                        "field_name": str,
                        "plugin_can_edit": bool,
                        "plugin_edit_framework": str | None,
                        "add_instructions": list[str]
                    },
                    ...
                ]
            },
            ...
        }
    """

    def __init__(
        self,
        note_uuid: str,
        cache_getter: Callable[[], Any] | None = None,
    ) -> None:
        """Initialize the template permissions checker.

        Args:
            note_uuid: UUID of the note to check permissions for
            cache_getter: Optional function to get the cache object (for testing)
        """
        self.note_uuid = note_uuid
        self._permissions_cache: dict[str, Any] | None = None
        self._cache_getter = cache_getter or _default_cache_getter

    def _load_permissions(self) -> dict[str, Any]:
        """Load permissions from cache (lazy, once per instance).

        Returns:
            Dictionary mapping command types to their permission structures,
            or empty dict if no permissions are stored or cache is unavailable.
        """
        if self._permissions_cache is not None:
            return self._permissions_cache

        try:
            cache = self._cache_getter()
            key = f"{COMMAND_PERMISSIONS_KEY_PREFIX}{self.note_uuid}"
            self._permissions_cache = cache.get(key, default={})
        except ImportError:
            log.warning("canvas_sdk.caching not available, template permissions disabled")
            self._permissions_cache = {}
        except Exception as e:
            log.warning(f"Could not load template permissions for {self.note_uuid}: {e}")
            self._permissions_cache = {}

        return self._permissions_cache

    def has_template_applied(self) -> bool:
        """Check if this note has a template with permissions applied.

        Returns:
            True if the note has template permissions stored, False otherwise.
        """
        return bool(self._load_permissions())

    def can_edit_command(self, command_type: str) -> bool:
        """Check if the command type can be edited by plugins.

        Args:
            command_type: The Canvas SDK command type name (e.g., "HistoryOfPresentIllnessCommand")

        Returns:
            True if the command can be edited, False if locked by template.
            Returns True if no template is applied.
        """
        permissions = self._load_permissions()
        if command_type not in permissions:
            return True  # No template restriction

        return bool(permissions[command_type].get("plugin_can_edit", True))

    def can_edit_command_by_class(self, hyperscribe_class_name: str) -> bool:
        """Check if a command can be edited, using Hyperscribe class name.

        Args:
            hyperscribe_class_name: The Hyperscribe command class name (e.g., "HistoryOfPresentIllness")

        Returns:
            True if the command can be edited, False if locked by template.
        """
        command_type = get_command_type(hyperscribe_class_name)
        return self.can_edit_command(command_type)

    def can_edit_field(self, command_type: str, field_name: str) -> bool:
        """Check if a specific field can be edited by plugins.

        A field is editable if:
        1. No template is applied (returns True), OR
        2. The command's plugin_can_edit is True, AND
        3. Either no field permission exists (inherits from command), OR
           the field's plugin_can_edit is True

        Args:
            command_type: The Canvas SDK command type name
            field_name: The field name to check

        Returns:
            True if the field can be edited, False if locked by template.
        """
        permissions = self._load_permissions()
        if command_type not in permissions:
            return True  # No template restriction

        cmd_perms = permissions[command_type]
        if not cmd_perms.get("plugin_can_edit", True):
            return False

        # Check field-level permissions
        for fp in cmd_perms.get("field_permissions", []):
            if fp.get("field_name") == field_name:
                return bool(fp.get("plugin_can_edit", True))

        # No specific field restriction, inherits from command
        return True

    def can_edit_field_by_class(self, hyperscribe_class_name: str, field_name: str) -> bool:
        """Check if a field can be edited, using Hyperscribe class name.

        Args:
            hyperscribe_class_name: The Hyperscribe command class name
            field_name: The field name to check

        Returns:
            True if the field can be edited, False if locked by template.
        """
        command_type = get_command_type(hyperscribe_class_name)
        return self.can_edit_field(command_type, field_name)

    def get_add_instructions(self, command_type: str, field_name: str) -> list[str]:
        """Get {add:} instructions for a field from the template.

        {add:} instructions tell plugins what content to add to a field.
        For example, "{add: symptoms}" tells the plugin to include symptom
        information in the generated content.

        Args:
            command_type: The Canvas SDK command type name
            field_name: The field name to get instructions for

        Returns:
            List of {add:} instruction strings, or empty list if none.
        """
        permissions = self._load_permissions()
        if command_type not in permissions:
            return []

        for fp in permissions[command_type].get("field_permissions", []):
            if fp.get("field_name") == field_name:
                instructions = fp.get("add_instructions", [])
                return list(instructions) if instructions else []

        return []

    def get_add_instructions_by_class(self, hyperscribe_class_name: str, field_name: str) -> list[str]:
        """Get {add:} instructions using Hyperscribe class name.

        Args:
            hyperscribe_class_name: The Hyperscribe command class name
            field_name: The field name to get instructions for

        Returns:
            List of {add:} instruction strings, or empty list if none.
        """
        command_type = get_command_type(hyperscribe_class_name)
        return self.get_add_instructions(command_type, field_name)

    def get_editable_fields(self, command_type: str) -> set[str] | None:
        """Get set of field names that are editable for a command type.

        Args:
            command_type: The Canvas SDK command type name

        Returns:
            Set of editable field names if template has restrictions,
            None if no template is applied (meaning all fields are editable).
        """
        permissions = self._load_permissions()
        if command_type not in permissions:
            return None  # No restrictions

        cmd_perms = permissions[command_type]
        if not cmd_perms.get("plugin_can_edit", True):
            return set()  # None editable

        editable = set()
        for fp in cmd_perms.get("field_permissions", []):
            if fp.get("plugin_can_edit", True):
                editable.add(fp.get("field_name"))

        return editable

    def get_all_command_types_with_restrictions(self) -> list[str]:
        """Get list of all command types that have template restrictions.

        Returns:
            List of command type names that have permissions defined.
        """
        return list(self._load_permissions().keys())

    def clear_cache(self) -> None:
        """Clear the cached permissions, forcing a reload on next access."""
        self._permissions_cache = None
