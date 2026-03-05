from __future__ import annotations

from time import time

import jwt
import requests

from hyperscribe.scribe.backend import ScribeAuthError

_BASE_URL = "https://us.api.nabla.com"
_TOKEN_URL = f"{_BASE_URL}/v1/core/server/oauth/token"

_TOKEN_REFRESH_MARGIN_SECONDS = 60
_JWT_EXPIRY_SECONDS = 300


class NablaAuth:
    def __init__(self, *, client_id: str, private_key: str) -> None:
        self.client_id = client_id
        self.private_key = private_key
        self._access_token: str = ""
        self._token_expires_at: float = 0.0

    @property
    def base_url(self) -> str:
        return _BASE_URL

    def get_access_token(self) -> str:
        """Return a cached or fresh backend (server) access token."""
        if self._access_token and time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return self._access_token
        return self._refresh_token()

    def get_user_tokens(self, external_id: str) -> tuple[str, str]:
        """Find or create a Nabla user by external_id, then return (access_token, refresh_token)."""
        user_id = self._get_or_create_user(external_id)
        return self._authenticate_user(user_id)

    def _get_or_create_user(self, external_id: str) -> str:
        """Find existing Nabla user by external_id, or create one."""
        backend_token = self.get_access_token()
        headers = {"Authorization": f"Bearer {backend_token}"}
        find_url = f"{_BASE_URL}/v1/core/server/users/find_by_external_id/{external_id}"
        try:
            response = requests.get(find_url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise ScribeAuthError(f"Nabla user lookup failed: {exc}") from exc

        if response.status_code == 200:
            return str(response.json()["id"])

        create_url = f"{_BASE_URL}/v1/core/server/users"
        try:
            response = requests.post(
                create_url,
                headers=headers,
                json={"external_id": external_id},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            raise ScribeAuthError(f"Nabla user creation failed: {exc}", status_code=status) from exc

        return str(response.json()["id"])

    def _authenticate_user(self, user_id: str) -> tuple[str, str]:
        """Get user access + refresh tokens via backend-to-user authentication."""
        backend_token = self.get_access_token()
        url = f"{_BASE_URL}/v1/core/server/jwt/authenticate/{user_id}"
        try:
            response = requests.post(
                url,
                headers={"Authorization": f"Bearer {backend_token}"},
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            raise ScribeAuthError(f"Nabla user auth failed: {exc}", status_code=status) from exc

        data = response.json()
        return str(data["access_token"]), str(data["refresh_token"])

    def _refresh_token(self) -> str:
        now = time()
        assertion = jwt.encode(
            {
                "iss": self.client_id,
                "sub": self.client_id,
                "aud": _TOKEN_URL,
                "exp": int(now) + _JWT_EXPIRY_SECONDS,
            },
            self.private_key,
            algorithm="RS256",
        )
        try:
            response = requests.post(
                _TOKEN_URL,
                json={
                    "grant_type": "client_credentials",
                    "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                    "client_assertion": assertion,
                },
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", 0) if hasattr(exc, "response") else 0
            raise ScribeAuthError(f"Nabla auth failed: {exc}", status_code=status) from exc

        data = response.json()
        self._access_token = data["access_token"]
        self._token_expires_at = now + data.get("expires_in", _JWT_EXPIRY_SECONDS)
        return self._access_token
