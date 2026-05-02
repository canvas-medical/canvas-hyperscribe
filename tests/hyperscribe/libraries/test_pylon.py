from types import SimpleNamespace
from unittest.mock import patch, call

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.pylon import Pylon


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_found(mock_post):
    mock_post.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [
                {"id": "acc-1", "name": "Other Instance"},
                {"id": "acc-2", "name": "my-instance production"},
            ]
        },
    )

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result == "acc-2"

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            json={"query": "my-instance"},
        )
    ]
    assert mock_post.mock_calls == calls


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_not_found_fallback_found(mock_post):
    no_match_response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [
                {"id": "acc-1", "name": "Other Instance"},
            ]
        },
    )
    fallback_response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [
                {"id": "acc-99", "name": "Canvas Test Account"},
            ]
        },
    )
    mock_post.side_effect = [no_match_response, fallback_response]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result == "acc-99"

    expected_headers = {
        "Authorization": "Bearer test-key",
        "Content-Type": "application/json",
    }
    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=expected_headers,
            json={"query": "my-instance"},
        ),
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=expected_headers,
            json={"query": Constants.VENDOR_PYLON_FALLBACK_ACCOUNT},
        ),
    ]
    assert mock_post.mock_calls == calls


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_not_found_fallback_not_found(mock_post):
    empty_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"data": []},
    )
    mock_post.side_effect = [empty_response, empty_response]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result is None

    assert mock_post.call_count == 2


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_api_error(mock_post):
    error_response = SimpleNamespace(
        status_code=500,
        text="Internal Server Error",
    )
    empty_response = SimpleNamespace(
        status_code=200,
        json=lambda: {"data": []},
    )
    mock_post.side_effect = [error_response, empty_response]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result is None

    assert mock_post.call_count == 2


@patch("hyperscribe.libraries.pylon.requests_post")
def test_create_issue_all_fields(mock_post):
    mock_response = SimpleNamespace(status_code=200)
    mock_post.return_value = mock_response

    pylon = Pylon("test-key")
    result = pylon.create_issue(
        title="Test Issue",
        body_html="<p>Body</p>",
        requester_email="user@example.com",
        account_id="acc-1",
        tags=["hyperscribe-feedback"],
    )
    assert result.status_code == 200

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/issues",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            json={
                "title": "Test Issue",
                "body_html": "<p>Body</p>",
                "account_id": "acc-1",
                "requester_email": "user@example.com",
                "tags": ["hyperscribe-feedback"],
            },
        )
    ]
    assert mock_post.mock_calls == calls


@patch("hyperscribe.libraries.pylon.requests_post")
def test_create_issue_minimal_fields(mock_post):
    mock_response = SimpleNamespace(status_code=200)
    mock_post.return_value = mock_response

    pylon = Pylon("test-key")
    result = pylon.create_issue(
        title="Test Issue",
        body_html="<p>Body</p>",
    )
    assert result.status_code == 200

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/issues",
            headers={
                "Authorization": "Bearer test-key",
                "Content-Type": "application/json",
            },
            json={
                "title": "Test Issue",
                "body_html": "<p>Body</p>",
            },
        )
    ]
    assert mock_post.mock_calls == calls
