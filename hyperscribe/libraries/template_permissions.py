"""Template permissions integration for note_templates plugin compatibility."""

from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any

from logger import log

if TYPE_CHECKING:
    from hyperscribe.commands.base import Base

# Cache key prefix (must match note_templates/utils/constants.py)
COMMAND_PERMISSIONS_KEY_PREFIX = "note_template_cmd_perms_"


# Shared prefix must match what brigade_note_templates/template_cache.py writes with.
# We bypass the plugin-scoped get_cache() (which auto-prefixes with the calling
# plugin's name) so that both plugins read/write the same cache keys.
SHARED_CACHE_PREFIX = "note_template_permissions"

try:
    from canvas_sdk.caching.client import get_cache as _get_cache_client
except ImportError:
    _get_cache_client = None


def _default_cache_getter() -> Any:
    """Default cache getter that uses a shared (non-plugin-scoped) cache prefix."""
    if _get_cache_client is None:
        raise ImportError("canvas_sdk.caching.client not available")
    return _get_cache_client(driver="plugins", prefix=SHARED_CACHE_PREFIX)


class TemplatePermissions:
    """Checks note-template edit permissions cached by the note_templates plugin.

    Cache key: ``note_template_cmd_perms_{note_uuid}``
    Value: ``{CommandType: {plugin_can_edit, field_permissions: [...]}}``
    """

    def __init__(self, note_uuid: str, cache_getter: Any = None) -> None:
        self.note_uuid = note_uuid
        self._permissions_cache: dict[str, Any] | None = None
        self._cache_getter = cache_getter or _default_cache_getter

    def _load_permissions(self) -> dict[str, Any]:
        """Load permissions from cache (lazy, once per instance)."""
        if self._permissions_cache is not None:
            return self._permissions_cache

        try:
            cache = self._cache_getter()
            key = f"{COMMAND_PERMISSIONS_KEY_PREFIX}{self.note_uuid}"
            self._permissions_cache = cache.get(key, default={})
            cmd_names = list(self._permissions_cache.keys()) if self._permissions_cache else []
            log.info(f"[TEMPLATE] Loaded permissions for {self.note_uuid}: {cmd_names}")
            if self._permissions_cache:
                perms_json = _json.dumps(self._permissions_cache, indent=2, default=str)
                log.info(f"[TEMPLATE] Permissions structure:\n{perms_json}")
        except ImportError:
            log.warning("canvas_sdk.caching not available, template permissions disabled")
            self._permissions_cache = {}
        except Exception as e:
            log.warning(f"Could not load template permissions for {self.note_uuid}: {e}")
            self._permissions_cache = {}

        return self._permissions_cache

    def has_template_applied(self) -> bool:
        """True if this note has template permissions stored."""
        return bool(self._load_permissions())

    def can_edit_command(self, command_class: type[Base]) -> bool:
        """True if the command type is editable (or absent from permissions)."""
        command_type = command_class.command_type()
        permissions = self._load_permissions()
        if command_type not in permissions:
            return True
        return bool(permissions[command_type].get("plugin_can_edit", True))

    def can_edit_field(self, command_class: type[Base], field_name: str) -> bool:
        """True if a specific field is editable (inherits from command if unset)."""
        command_type = command_class.command_type()
        permissions = self._load_permissions()
        if command_type not in permissions:
            return True

        cmd_perms = permissions[command_type]
        if not cmd_perms.get("plugin_can_edit", True):
            return False

        for fp in cmd_perms.get("field_permissions", []):
            if fp.get("field_name") == field_name:
                return bool(fp.get("plugin_can_edit", True))

        return True

    def get_add_instructions(self, command_class: type[Base], field_name: str) -> list[str]:
        """Return {add:} instruction strings for a field, or empty list."""
        command_type = command_class.command_type()
        permissions = self._load_permissions()
        if command_type not in permissions:
            return []

        for fp in permissions[command_type].get("field_permissions", []):
            if fp.get("field_name") == field_name:
                instructions = fp.get("add_instructions", [])
                return list(instructions) if instructions else []

        return []

    def get_edit_framework(self, command_class: type[Base], field_name: str) -> str | None:
        """Return the plugin_edit_framework for a field, or None."""
        command_type = command_class.command_type()
        permissions = self._load_permissions()
        if command_type not in permissions:
            return None

        for fp in permissions[command_type].get("field_permissions", []):
            if fp.get("field_name") == field_name:
                framework = fp.get("plugin_edit_framework")
                return str(framework) if framework else None

        return None

    def clear_cache(self) -> None:
        """Clear the cached permissions, forcing a reload on next access."""
        self._permissions_cache = None
