"""Template permissions integration for note_templates plugin compatibility."""

from __future__ import annotations

import json as _json
from typing import TYPE_CHECKING, Any, Callable

from logger import log

from hyperscribe.libraries.constants import Constants

from canvas_sdk.caching.client import get_cache as _get_cache_client

if TYPE_CHECKING:
    from canvas_sdk.caching.base import Cache


class TemplatePermissions:
    """Loads note-template edit permissions cached by the note_templates plugin.

    Cache key: ``note_template_cmd_perms_{note_uuid}``
    Value: ``{CommandType: {plugin_can_edit, field_permissions: [...]}}``
    """

    def __init__(self, note_uuid: str, cache_getter: Callable[[], Cache] | None = None) -> None:
        self.note_uuid = note_uuid
        self._permissions_cache: dict[str, Any] | None = None
        self._cache_getter = cache_getter or self.default_cache_getter

    @classmethod
    def default_cache_getter(cls) -> Cache:
        """Default cache getter that uses a shared (non-plugin-scoped) cache prefix."""
        return _get_cache_client(driver="plugins", prefix=Constants.TEMPLATE_SHARED_CACHE_PREFIX)

    def load_permissions(self) -> dict[str, Any]:
        """Load permissions from cache (lazy, once per instance)."""
        if self._permissions_cache is not None:
            return self._permissions_cache

        try:
            cache = self._cache_getter()
            key = f"{Constants.TEMPLATE_COMMAND_PERMISSIONS_KEY_PREFIX}{self.note_uuid}"
            self._permissions_cache = cache.get(key, default={})
            cmd_names = list(self._permissions_cache.keys()) if self._permissions_cache else []
            log.info(f"[TEMPLATE] Loaded permissions for {self.note_uuid}: {cmd_names}")
            if self._permissions_cache:
                perms_json = _json.dumps(self._permissions_cache, indent=2, default=str)
                log.info(f"[TEMPLATE] Permissions structure:\n{perms_json}")
        except Exception as e:
            log.warning(f"Could not load template permissions for {self.note_uuid}: {e}")
            self._permissions_cache = {}

        return self._permissions_cache
