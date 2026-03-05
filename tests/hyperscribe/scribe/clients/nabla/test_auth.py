from time import time
from unittest.mock import MagicMock, patch

import pytest
import requests as requests_lib

from hyperscribe.scribe.backend import ScribeAuthError
from hyperscribe.scribe.clients.nabla.auth import NablaAuth


def test_get_access_token_refreshes_on_first_call() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    with patch.object(auth, "_refresh_token", return_value="tok-1") as mock_refresh:
        token = auth.get_access_token()
    assert token == "tok-1"
    mock_refresh.assert_called_once()


def test_get_access_token_returns_cached() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "cached-token"
    auth._token_expires_at = time() + 600
    with patch.object(auth, "_refresh_token") as mock_refresh:
        token = auth.get_access_token()
    assert token == "cached-token"
    mock_refresh.assert_not_called()


def test_get_access_token_refreshes_when_near_expiry() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "old-token"
    auth._token_expires_at = time() + 10  # within margin
    with patch.object(auth, "_refresh_token", return_value="new-token") as mock_refresh:
        token = auth.get_access_token()
    assert token == "new-token"
    mock_refresh.assert_called_once()


def test_refresh_token_success() -> None:
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
    assert call_kwargs.kwargs["json"]["client_assertion"] == "jwt-assertion"
    assert call_kwargs.kwargs["json"]["grant_type"] == "client_credentials"
    assert (
        call_kwargs.kwargs["json"]["client_assertion_type"] == "urn:ietf:params:oauth:client-assertion-type:jwt-bearer"
    )


def test_refresh_token_builds_correct_jwt() -> None:
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


def test_refresh_token_http_error() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests_lib.HTTPError(response=mock_response)

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=mock_response):
        with patch("hyperscribe.scribe.clients.nabla.auth.jwt.encode", return_value="jwt"):
            with pytest.raises(ScribeAuthError, match="Nabla auth failed"):
                auth._refresh_token()


# --- User provisioning ---


def test_get_or_create_user_found() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "backend-token"
    auth._token_expires_at = time() + 600

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"id": "nabla-user-123"}

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.get", return_value=mock_response) as mock_get:
        user_id = auth._get_or_create_user("staff-key-abc")

    assert user_id == "nabla-user-123"
    assert "find_by_external_id/staff-key-abc" in mock_get.call_args.args[0]


def test_get_or_create_user_creates_when_not_found() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "backend-token"
    auth._token_expires_at = time() + 600

    find_response = MagicMock()
    find_response.status_code = 400  # not found

    create_response = MagicMock()
    create_response.status_code = 200
    create_response.json.return_value = {"id": "new-user-456"}
    create_response.raise_for_status.return_value = None

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.get", return_value=find_response):
        with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=create_response) as mock_post:
            user_id = auth._get_or_create_user("staff-key-xyz")

    assert user_id == "new-user-456"
    assert mock_post.call_args.kwargs["json"] == {"external_id": "staff-key-xyz"}


def test_get_or_create_user_create_failure() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "backend-token"
    auth._token_expires_at = time() + 600

    find_response = MagicMock()
    find_response.status_code = 400

    create_response = MagicMock()
    create_response.status_code = 500
    create_response.raise_for_status.side_effect = requests_lib.HTTPError(response=create_response)

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.get", return_value=find_response):
        with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=create_response):
            with pytest.raises(ScribeAuthError, match="Nabla user creation failed"):
                auth._get_or_create_user("bad-user")


def test_authenticate_user_success() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "backend-token"
    auth._token_expires_at = time() + 600

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "user-at", "refresh_token": "user-rt"}
    mock_response.raise_for_status.return_value = None

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=mock_response) as mock_post:
        access_token, refresh_token = auth._authenticate_user("nabla-user-123")

    assert access_token == "user-at"
    assert refresh_token == "user-rt"
    assert "jwt/authenticate/nabla-user-123" in mock_post.call_args.args[0]


def test_authenticate_user_failure() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "backend-token"
    auth._token_expires_at = time() + 600

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests_lib.HTTPError(response=mock_response)

    with patch("hyperscribe.scribe.clients.nabla.auth.requests.post", return_value=mock_response):
        with pytest.raises(ScribeAuthError, match="Nabla user auth failed"):
            auth._authenticate_user("bad-user-id")


def test_get_user_tokens_full_flow() -> None:
    auth = NablaAuth(client_id="cid", private_key="pk")
    auth._access_token = "backend-token"
    auth._token_expires_at = time() + 600

    with patch.object(auth, "_get_or_create_user", return_value="nabla-user-id") as mock_create:
        with patch.object(auth, "_authenticate_user", return_value=("u-at", "u-rt")) as mock_auth:
            access_token, refresh_token = auth.get_user_tokens("staff-key")

    assert access_token == "u-at"
    assert refresh_token == "u-rt"
    mock_create.assert_called_once_with("staff-key")
    mock_auth.assert_called_once_with("nabla-user-id")
