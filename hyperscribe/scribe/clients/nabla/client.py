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
            # Per Nabla docs, the per-request version OVERRIDE header is
            # "X-Nabla-Api-Version" ("nabla-api-version" is the query-param form).
            # Sending the wrong header name silently falls back to the org's
            # pinned version, so the override never applied to REST calls.
            "X-Nabla-Api-Version": self._api_version,
        }

    _FRIENDLY_ERRORS: dict[str, str] = {
        "NOTE_GENERATION_TRANSCRIPT_TOO_SHORT": (
            "The transcript is too short to generate a note. Please record a longer conversation and try again."
        ),
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

    @classmethod
    def _friendly_message(cls, exc: requests.RequestException) -> str | None:
        response = getattr(exc, "response", None)
        if response is None:
            return None
        try:
            body: dict[str, Any] = response.json()
            name = body.get("name", "")
            return cls._FRIENDLY_ERRORS.get(name)
        except (ValueError, AttributeError):
            return None

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
            friendly = self._friendly_message(exc)
            if friendly:
                raise ScribeNoteGenerationError(friendly, status_code=status) from exc
            detail = self._extract_error_detail(exc)
            raise ScribeNoteGenerationError(f"Nabla generate note failed: {exc}{detail}", status_code=status) from exc
        result: dict[str, Any] = response.json()
        return result

    def get_note_template(self, template_key: str, *, locale: str = "ENGLISH_US") -> dict[str, Any]:
        """Fetch a note template's definition (sections + supported_customization_options).

        Backs the capability check for whether a template/section supports an option
        like ``split_by_problem`` at the current API version (added 2026-06-12). Used
        for diagnostics/UAT rather than the hot path — prefer this over discovering an
        unsupported customization via a 400 at generate-note time.
        """
        url = f"{self._auth.base_url}/v1/core/server/generate-note/templates/{template_key}"
        try:
            response = self._session.get(
                url,
                headers=self._headers(),
                params={"locale": locale},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            detail = self._extract_error_detail(exc)
            raise ScribeNoteGenerationError(
                f"Nabla get note template failed: {exc}{detail}", status_code=status
            ) from exc
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
