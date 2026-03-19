from unittest.mock import MagicMock, patch

import pytest
import requests

from hyperscribe.scribe.backend import (
    ScribeNormalizationError,
    ScribeNoteGenerationError,
)
from hyperscribe.scribe.clients.nabla.auth import NablaAuth
from hyperscribe.scribe.clients.nabla.client import NablaClient


def _make_client() -> tuple[NablaClient, MagicMock]:
    auth = MagicMock(spec=NablaAuth)
    auth.base_url = "https://us.nabla.com/api/server"
    auth.get_access_token.return_value = "test-token"
    return NablaClient(auth, api_version="2025-05-21"), auth


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
    with patch.object(client._session, "post", return_value=_mock_response(expected)) as mock_post:
        result = client.generate_note({"transcript": {}})

    assert result == expected
    url = mock_post.call_args.args[0]
    assert "/v1/core/server/generate-note" in url


def test_generate_note_error():
    client, _ = _make_client()
    with patch.object(client._session, "post", return_value=_mock_error_response(500)):
        with pytest.raises(ScribeNoteGenerationError, match="generate note failed"):
            client.generate_note({})


def test_generate_note_transcript_too_short():
    client, _ = _make_client()
    response = MagicMock()
    response.status_code = 422
    response.json.return_value = {
        "message": "We can't generate the note when the transcript is too short.",
        "code": 83005,
        "name": "NOTE_GENERATION_TRANSCRIPT_TOO_SHORT",
    }
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    with patch.object(client._session, "post", return_value=response):
        with pytest.raises(ScribeNoteGenerationError, match="too short to generate a note"):
            client.generate_note({})


def test_generate_note_unknown_error_code_falls_through():
    client, _ = _make_client()
    response = MagicMock()
    response.status_code = 422
    response.json.return_value = {"name": "SOME_UNKNOWN_ERROR", "message": "weird"}
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    with patch.object(client._session, "post", return_value=response):
        with pytest.raises(ScribeNoteGenerationError, match="generate note failed"):
            client.generate_note({})


def test_generate_normalized_data_success():
    client, _ = _make_client()
    expected = {"conditions": [], "observations": []}
    with patch.object(client._session, "post", return_value=_mock_response(expected)) as mock_post:
        result = client.generate_normalized_data({"note": {}})

    assert result == expected
    url = mock_post.call_args.args[0]
    assert "/v1/core/server/generate-normalized-data" in url


def test_generate_normalized_data_error():
    client, _ = _make_client()
    with patch.object(client._session, "post", return_value=_mock_error_response(503)):
        with pytest.raises(ScribeNormalizationError, match="generate normalized data failed"):
            client.generate_normalized_data({})


def test_headers_include_bearer_token():
    client, auth = _make_client()
    auth.get_access_token.return_value = "my-token"
    headers = client._headers()
    assert headers == {"Authorization": "Bearer my-token", "nabla-api-version": "2025-05-21"}
