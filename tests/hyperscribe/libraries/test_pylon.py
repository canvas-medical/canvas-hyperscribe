from types import SimpleNamespace
from unittest.mock import patch, call

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.pylon import Pylon

EXPECTED_HEADERS = {
    "Authorization": "Bearer test-key",
    "Content-Type": "application/json",
}


def _search_json(query: str) -> dict:
    return {
        "filter": {
            "field": "name",
            "operator": "string_contains",
            "value": query,
        },
        "limit": 10,
    }


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_exact_match(mock_post):
    mock_post.return_value = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [{"id": "acc-1", "name": "my-instance"}],
        },
    )

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result == "acc-1"

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=EXPECTED_HEADERS,
            json=_search_json("my-instance"),
        )
    ]
    assert mock_post.mock_calls == calls


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_dehyphenated_match(mock_post):
    no_match = SimpleNamespace(status_code=200, json=lambda: {"data": []})
    match = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [{"id": "acc-2", "name": "MyInstance"}],
        },
    )
    mock_post.side_effect = [no_match, match]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result == "acc-2"

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=EXPECTED_HEADERS,
            json=_search_json("my-instance"),
        ),
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=EXPECTED_HEADERS,
            json=_search_json("MyInstance"),
        ),
    ]
    assert mock_post.mock_calls == calls


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_fallback_found(mock_post):
    no_match = SimpleNamespace(status_code=200, json=lambda: {"data": []})
    fallback_match = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [{"id": "acc-99", "name": "Canvas Test Account"}],
        },
    )
    mock_post.side_effect = [no_match, no_match, fallback_match]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result == "acc-99"

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=EXPECTED_HEADERS,
            json=_search_json("my-instance"),
        ),
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=EXPECTED_HEADERS,
            json=_search_json("MyInstance"),
        ),
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/accounts/search",
            headers=EXPECTED_HEADERS,
            json=_search_json(Constants.VENDOR_PYLON_FALLBACK_ACCOUNT),
        ),
    ]
    assert mock_post.mock_calls == calls


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_all_miss(mock_post):
    no_match = SimpleNamespace(status_code=200, json=lambda: {"data": []})
    mock_post.side_effect = [no_match, no_match, no_match]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result is None
    assert mock_post.call_count == 3


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_api_error_falls_through(mock_post):
    error = SimpleNamespace(status_code=500, text="Internal Server Error")
    no_match = SimpleNamespace(status_code=200, json=lambda: {"data": []})
    mock_post.side_effect = [error, no_match, no_match]

    pylon = Pylon("test-key")
    result = pylon.search_account("my-instance")
    assert result is None
    assert mock_post.call_count == 3


@patch("hyperscribe.libraries.pylon.requests_post")
def test_search_account_no_hyphens_skips_dehyphenated(mock_post):
    no_match = SimpleNamespace(status_code=200, json=lambda: {"data": []})
    fallback_match = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "data": [{"id": "acc-99", "name": "Canvas Test Account"}],
        },
    )
    # No hyphens means only 2 searches: exact + fallback (no dehyphenated)
    mock_post.side_effect = [no_match, fallback_match]

    pylon = Pylon("test-key")
    result = pylon.search_account("myinstance")
    assert result == "acc-99"
    assert mock_post.call_count == 2


@patch("hyperscribe.libraries.pylon.requests_post")
def test_create_issue_all_fields(mock_post):
    mock_post.return_value = SimpleNamespace(status_code=200)

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
            headers=EXPECTED_HEADERS,
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
    mock_post.return_value = SimpleNamespace(status_code=200)

    pylon = Pylon("test-key")
    result = pylon.create_issue(
        title="Test Issue",
        body_html="<p>Body</p>",
    )
    assert result.status_code == 200

    calls = [
        call(
            f"{Constants.VENDOR_PYLON_API_BASE_URL}/issues",
            headers=EXPECTED_HEADERS,
            json={
                "title": "Test Issue",
                "body_html": "<p>Body</p>",
            },
        )
    ]
    assert mock_post.mock_calls == calls
