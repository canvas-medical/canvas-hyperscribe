from unittest.mock import MagicMock, patch

import pytest
import requests

from hyperscribe.scribe.errors import (
    ScribeNormalizationError,
    ScribeNoteGenerationError,
)
from hyperscribe.scribe.nabla.auth import NablaAuth
from hyperscribe.scribe.nabla.client import NablaClient


def _make_client() -> tuple[NablaClient, MagicMock]:
    auth = MagicMock(spec=NablaAuth)
    auth.base_url = "https://us.nabla.com/api/server"
    auth.get_access_token.return_value = "test-token"
    return NablaClient(auth), auth


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    response = MagicMock()
    response.json.return_value = json_data
    response.status_code = status_code
    response.raise_for_status.return_value = None
    return response


def _mock_error_response(status_code: int = 500) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    return response


def test_generate_note_success():
    client, _ = _make_client()
    expected = {"title": "SOAP Note", "sections": []}
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_response(expected)) as mock_post:
        result = client.generate_note({"transcript": {}})

    assert result == expected
    assert "generate-note" in mock_post.call_args.args[0]


def test_generate_note_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_error_response(500)):
        with pytest.raises(ScribeNoteGenerationError, match="generate note failed"):
            client.generate_note({})


def test_generate_normalized_data_success():
    client, _ = _make_client()
    expected = {"conditions": [], "observations": []}
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_response(expected)) as mock_post:
        result = client.generate_normalized_data({"note": {}})

    assert result == expected
    assert "generate-normalized-data" in mock_post.call_args.args[0]


def test_generate_normalized_data_error():
    client, _ = _make_client()
    with patch("hyperscribe.scribe.nabla.client.requests.post", return_value=_mock_error_response(503)):
        with pytest.raises(ScribeNormalizationError, match="generate normalized data failed"):
            client.generate_normalized_data({})


def test_headers_include_bearer_token():
    client, auth = _make_client()
    auth.get_access_token.return_value = "my-token"
    headers = client._headers()
    assert headers == {"Authorization": "Bearer my-token"}
