from time import time
from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.backend import ScribeAuthError
from hyperscribe.scribe.clients.nabla.auth import (
    NablaAuth,
)


def test_base_url():
    auth = NablaAuth(client_id="cid", private_key="pk")
    assert auth.base_url == "https://us.nabla.com/api/server"


def test_get_access_token_refreshes_on_first_call():
    auth = NablaAuth(client_id="cid", private_key="pk")
    with patch.object(auth, "_refresh_token", return_value="tok-1") as mock_refresh:
        token = auth.get_access_token()
    assert token == "tok-1"
    mock_refresh.assert_called_once()


def test_get_access_token_returns_cached():
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "cached-token"
    auth._token_expires_at = time() + 600
    with patch.object(auth, "_refresh_token") as mock_refresh:
        token = auth.get_access_token()
    assert token == "cached-token"
    mock_refresh.assert_not_called()


def test_get_access_token_refreshes_when_near_expiry():
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "old-token"
    auth._token_expires_at = time() + 10  # within margin
    with patch.object(auth, "_refresh_token", return_value="new-token") as mock_refresh:
        token = auth.get_access_token()
    assert token == "new-token"
    mock_refresh.assert_called_once()


def test_refresh_token_success():
    auth = NablaAuth(client_id="cid", private_key="pk")
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "fresh-token", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=mock_response) as mock_post:
        with patch("hyperscribe.scribe.clients.nabla.auth.jwt.encode", return_value="jwt-assertion"):
            token = auth._refresh_token()

    assert token == "fresh-token"
    assert auth._access_token == "fresh-token"
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "v1/core/server/oauth/token" in call_kwargs.args[0]
    assert call_kwargs.kwargs["data"]["assertion"] == "jwt-assertion"


def test_refresh_token_builds_correct_jwt():
    auth = NablaAuth(client_id="my-client", private_key="pk")
    mock_response = MagicMock()
    mock_response.json.return_value = {"access_token": "tok", "expires_in": 3600}
    mock_response.raise_for_status.return_value = None

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=mock_response):
        with patch("hyperscribe.scribe.clients.nabla.auth.jwt.encode", return_value="jwt") as mock_encode:
            auth._refresh_token()

    jwt_payload = mock_encode.call_args.args[0]
    assert jwt_payload["iss"] == "my-client"
    assert jwt_payload["sub"] == "my-client"
    assert "oauth/token" in jwt_payload["aud"]
    assert mock_encode.call_args.kwargs["algorithm"] == "RS256"


def test_refresh_token_http_error():
    auth = NablaAuth(client_id="cid", private_key="pk")
    import requests

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests.HTTPError(response=mock_response)

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=mock_response):
        with patch("hyperscribe.scribe.clients.nabla.auth.jwt.encode", return_value="jwt"):
            with pytest.raises(ScribeAuthError, match="Nabla auth failed"):
                auth._refresh_token()
