"""Template permissions integration for note_templates plugin compatibility."""

from __future__ import annotations

import json as _json
from typing import Any

from logger import log

from hyperscribe.libraries.constants import Constants

from canvas_sdk.caching.base import Cache
from canvas_sdk.caching.client import get_cache as _get_cache_client


class TemplatePermissions:
    """Loads note-template edit permissions cached by the note_templates plugin.

    Cache key: ``note_template_cmd_perms_{note_uuid}``
    Value: ``{CommandType: {plugin_can_edit, field_permissions: [...]}}``
    """

    PERMISSIONS: dict[str, dict[str, Any]] = {}

    @classmethod
    def default_cache_getter(cls) -> Cache:
        """Default cache getter that uses a shared (non-plugin-scoped) cache prefix."""
        return _get_cache_client(driver="plugins", prefix=Constants.TEMPLATE_SHARED_CACHE_PREFIX)

    def __init__(self, note_uuid: str) -> None:
        self.note_uuid = note_uuid

    def __del__(self) -> None:
        if self.note_uuid in self.PERMISSIONS:
            del self.PERMISSIONS[self.note_uuid]

    def load_permissions(self) -> dict[str, Any]:
        """Load permissions from cache (lazy, once per note_uuid)."""
        if self.note_uuid not in self.PERMISSIONS:
            try:
                key = f"{Constants.TEMPLATE_COMMAND_PERMISSIONS_KEY_PREFIX}{self.note_uuid}"
                self.PERMISSIONS[self.note_uuid] = self.default_cache_getter().get(key, default={})

                cmd_names = []
                if self.PERMISSIONS[self.note_uuid]:
                    cmd_names = list(self.PERMISSIONS[self.note_uuid].keys())
                log.info(f"[TEMPLATE] Loaded permissions for {self.note_uuid}: {cmd_names}")

                if self.PERMISSIONS[self.note_uuid]:
                    perms_json = _json.dumps(self.PERMISSIONS[self.note_uuid], indent=2, default=str)
                    log.info(f"[TEMPLATE] Permissions structure:\n{perms_json}")

            except Exception as e:
                log.warning(f"Could not load template permissions for {self.note_uuid}: {e}")
                self.PERMISSIONS[self.note_uuid] = {}

        return self.PERMISSIONS[self.note_uuid]
