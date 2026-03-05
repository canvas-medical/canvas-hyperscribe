from __future__ import annotations

from typing import Any

import requests

from hyperscribe.scribe.errors import (
    ScribeNormalizationError,
    ScribeNoteGenerationError,
)
from hyperscribe.scribe.nabla.auth import NablaAuth


class NablaClient:
    def __init__(self, auth: NablaAuth) -> None:
        self._auth = auth

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth.get_access_token()}",
        }

    def generate_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self._auth.base_url}/v1/copilot-api/server/generate-note",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            raise ScribeNoteGenerationError(f"Nabla generate note failed: {exc}", status_code=status) from exc
        result: dict[str, Any] = response.json()
        return result

    def generate_normalized_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = requests.post(
                f"{self._auth.base_url}/v1/copilot-api/server/generate-normalized-data",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            raise ScribeNormalizationError(f"Nabla generate normalized data failed: {exc}", status_code=status) from exc
        result: dict[str, Any] = response.json()
        return result
