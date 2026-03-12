from __future__ import annotations

from typing import Any

import requests

from hyperscribe.scribe.backend import (
    ScribeNormalizationError,
    ScribeNoteGenerationError,
)
from hyperscribe.scribe.clients.nabla.auth import NablaAuth


class NablaClient:
    def __init__(self, auth: NablaAuth, *, api_version: str) -> None:
        self._auth = auth
        self._api_version = api_version
        self._session = requests.Session()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._auth.get_access_token()}",
            "nabla-api-version": self._api_version,
        }

    @staticmethod
    def _extract_error_detail(exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return ""
        try:
            body = response.json()
            return f" | detail: {body}"
        except (ValueError, AttributeError):
            text = getattr(response, "text", "")
            return f" | body: {text[:500]}" if text else ""

    def generate_note(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._session.post(
                f"{self._auth.base_url}/v1/core/server/generate-note",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            detail = self._extract_error_detail(exc)
            raise ScribeNoteGenerationError(f"Nabla generate note failed: {exc}{detail}", status_code=status) from exc
        result: dict[str, Any] = response.json()
        return result

    def generate_normalized_data(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._auth.base_url}/v1/core/server/generate-normalized-data"
        try:
            response = self._session.post(
                url,
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            detail = self._extract_error_detail(exc)
            raise ScribeNormalizationError(
                f"Nabla generate normalized data failed: {exc}{detail}", status_code=status
            ) from exc
        result: dict[str, Any] = response.json()
        return result
