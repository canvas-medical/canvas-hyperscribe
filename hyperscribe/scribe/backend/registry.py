from __future__ import annotations

import json

from hyperscribe.libraries.constants import Constants
from hyperscribe.scribe.backend.base import ScribeBackend
from hyperscribe.scribe.backend.errors import ScribeError

_REGISTRY: dict[str, type[ScribeBackend]] = {}


def register_backend(vendor: str, cls: type[ScribeBackend]) -> None:
    _REGISTRY[vendor.lower()] = cls


def get_backend_from_secrets(secrets: dict[str, str]) -> ScribeBackend:
    """Create a scribe backend from the plugin secrets dict.

    Parses the ScribeBackend JSON secret, uses "vendor" to pick the backend class,
    and passes the remaining fields as **kwargs to the backend constructor.
    """
    raw = secrets.get(Constants.SECRET_SCRIBE_BACKEND, "{}")
    config = json.loads(raw, strict=False) if isinstance(raw, str) else raw
    vendor = config.pop("vendor", "").lower()
    backend_cls = _REGISTRY.get(vendor)
    if backend_cls is None:
        raise ScribeError(f"Unknown scribe vendor: {vendor!r}")
    return backend_cls(**config)
