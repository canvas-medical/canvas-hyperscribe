from __future__ import annotations

from dataclasses import dataclass, field
from time import time

import jwt
import requests

from hyperscribe.scribe.errors import ScribeAuthError

_NABLA_BASE_URLS: dict[str, str] = {
    "us": "https://us.nabla.com/api/server",
    "eu": "https://eu.nabla.com/api/server",
}

_TOKEN_REFRESH_MARGIN_SECONDS = 60
_JWT_EXPIRY_SECONDS = 300


@dataclass
class NablaAuth:
    region: str
    client_id: str
    private_key: str
    _access_token: str = field(default="", init=False, repr=False)
    _token_expires_at: float = field(default=0.0, init=False, repr=False)

    @property
    def base_url(self) -> str:
        url = _NABLA_BASE_URLS.get(self.region.lower())
        if url is None:
            raise ScribeAuthError(f"Unknown Nabla region: {self.region!r}")
        return url

    def get_access_token(self) -> str:
        if self._access_token and time() < self._token_expires_at - _TOKEN_REFRESH_MARGIN_SECONDS:
            return self._access_token
        return self._refresh_token()

    def _refresh_token(self) -> str:
        now = time()
        assertion = jwt.encode(
            {
                "iss": self.client_id,
                "sub": self.client_id,
                "aud": f"{self.base_url}/v1/core/server/oauth/token",
                "iat": int(now),
                "exp": int(now) + _JWT_EXPIRY_SECONDS,
            },
            self.private_key,
            algorithm="RS256",
        )
        try:
            response = requests.post(
                f"{self.base_url}/v1/core/server/oauth/token",
                data={
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": assertion,
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
