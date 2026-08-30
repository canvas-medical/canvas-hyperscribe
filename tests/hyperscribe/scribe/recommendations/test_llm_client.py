from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest

from hyperscribe.scribe.recommendations._llm_client import (
    DEFAULT_EFFORT,
    DEFAULT_MODEL,
    ScribeLlmAnthropic,
    ScribeLlmSettings,
    classify_transport_error,
    make_fill_client,
)
from hyperscribe.scribe.recommendations.schemas import QuestionnaireFillResult


def test_settings_never_send_a_sampling_parameter() -> None:
    """Current-generation models reject temperature/top_p/top_k with a 400, and the SDK's
    own LlmSettingsAnthropic always emits temperature. That incompatibility is the whole
    reason this class exists, so it is worth pinning."""
    payload = ScribeLlmSettings(api_key="k", model=DEFAULT_MODEL).to_dict()
    assert "temperature" not in payload
    assert "top_p" not in payload
    assert "top_k" not in payload
    assert payload["model"] == DEFAULT_MODEL
    assert payload["thinking"] == {"type": "adaptive"}
    assert payload["output_config"] == {"effort": DEFAULT_EFFORT}


def test_settings_reject_an_unknown_effort() -> None:
    """Effort comes from an operator-set secret, so a typo must not 400 every request."""
    assert ScribeLlmSettings(api_key="k", model="m", effort="turbo").to_dict()["output_config"] == {
        "effort": DEFAULT_EFFORT
    }


def test_settings_accept_a_valid_effort() -> None:
    assert ScribeLlmSettings(api_key="k", model="m", effort="xhigh").to_dict()["output_config"] == {"effort": "xhigh"}


def test_cache_control_lands_on_the_transcript_block() -> None:
    """The system prompt and transcript form the stable prefix; the per-chunk definition
    must stay outside it or every chunk would write a new cache entry."""
    client = make_fill_client("k", cache_index=1)
    client.set_system_prompt(["system"])
    client.set_user_prompt(["transcript"])
    client.set_user_prompt(["definition"])

    blocks = client.to_dict()["messages"][0]["content"]
    assert [b["text"] for b in blocks] == ["system", "transcript", "definition"]
    assert "cache_control" not in blocks[0]
    assert blocks[1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in blocks[2]


def test_no_cache_control_when_no_index_is_given() -> None:
    client = make_fill_client("k")
    client.set_system_prompt(["system"])
    client.set_user_prompt(["transcript"])
    assert all("cache_control" not in b for b in client.to_dict()["messages"][0]["content"])


def _http_response(status: int, body: dict) -> MagicMock:
    response = MagicMock()
    response.status_code = status
    response.text = json.dumps(body)
    return response


def test_structured_output_is_read_from_the_tool_use_block_not_the_first_one() -> None:
    """The SDK reads content[0]. With thinking on, content[0] is a thinking block, so
    that lookup returns {} and every questionnaire comes back empty. This is the bug the
    reimplemented request() exists to avoid."""
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.set_schema(QuestionnaireFillResult)
    client.http.post = MagicMock(  # type: ignore[method-assign]
        return_value=_http_response(
            200,
            {
                "content": [
                    {"type": "thinking", "thinking": "considering the transcript"},
                    {"type": "tool_use", "name": "QuestionnaireFillResult", "input": {"questionnaireDbid": 7}},
                ],
                "usage": {"input_tokens": 10, "output_tokens": 4},
            },
        )
    )

    response = client.request()

    assert json.loads(response.response) == {"questionnaireDbid": 7}


def test_plain_text_output_concatenates_text_blocks_and_skips_thinking() -> None:
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(  # type: ignore[method-assign]
        return_value=_http_response(
            200,
            {"content": [{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "answer"}]},
        )
    )
    assert client.request().response == "answer"


def test_request_captures_the_full_usage_block() -> None:
    """The SDK narrows usage to prompt/generated, dropping cache_read_input_tokens — the
    one number that says whether the prefix caching is actually working."""
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(  # type: ignore[method-assign]
        return_value=_http_response(
            200,
            {
                "content": [{"type": "text", "text": "ok"}],
                "usage": {"input_tokens": 12, "output_tokens": 3, "cache_read_input_tokens": 900},
            },
        )
    )

    response = client.request()

    assert client.last_usage["cache_read_input_tokens"] == 900
    assert response.tokens.prompt == 12
    assert response.tokens.generated == 3


def test_a_non_200_is_returned_not_raised() -> None:
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(return_value=_http_response(429, {"error": "slow down"}))  # type: ignore[method-assign]
    assert client.request().code == HTTPStatus.TOO_MANY_REQUESTS


def test_a_transport_failure_becomes_a_bad_request() -> None:
    """Mirrors the SDK, and matters because the sandbox's hardcoded 30s POST timeout
    arrives here as an exception."""
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(side_effect=RuntimeError("timed out"))  # type: ignore[method-assign]

    response = client.request()

    assert response.code == HTTPStatus.BAD_REQUEST
    assert "timed out" in response.response


def test_an_unparseable_body_becomes_a_bad_request() -> None:
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    bad = MagicMock()
    bad.status_code = 200
    bad.text = "not json"
    client.http.post = MagicMock(return_value=bad)  # type: ignore[method-assign]
    assert client.request().code == HTTPStatus.BAD_REQUEST


def test_usage_is_reset_between_requests() -> None:
    """A failed call must not leave the previous call's numbers on the client, or the run
    telemetry would double-count."""
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(  # type: ignore[method-assign]
        return_value=_http_response(200, {"content": [{"type": "text", "text": "ok"}], "usage": {"input_tokens": 5}})
    )
    client.request()
    assert client.last_usage == {"input_tokens": 5}

    client.http.post = MagicMock(return_value=_http_response(500, {}))  # type: ignore[method-assign]
    client.request()
    assert client.last_usage == {}


# --- transport error classification -----------------------------------------
#
# Collapsing every transport failure into BAD_REQUEST made a 30s timeout read as "your
# request was malformed", which points at the wrong fix: the cause is a chunk pushing past
# the SDK's fixed ceiling, not bad code. Classified by exception class NAME because the
# sandbox's ALLOWED_MODULES does not expose `Timeout` or `ConnectionError` from `requests`,
# so they cannot be imported to catch.


class _ReadTimeout(Exception):
    pass


class _ConnectTimeout(Exception):
    pass


class _ConnectionError(Exception):
    pass


class _SSLError(Exception):
    pass


class _InvalidHeader(Exception):
    pass


@pytest.mark.parametrize(
    "name, expected_code, expected_kind",
    [
        ("ReadTimeout", HTTPStatus.REQUEST_TIMEOUT, "timeout"),
        ("ConnectTimeout", HTTPStatus.REQUEST_TIMEOUT, "timeout"),
        ("Timeout", HTTPStatus.REQUEST_TIMEOUT, "timeout"),
        ("ConnectionError", HTTPStatus.SERVICE_UNAVAILABLE, "connection_error"),
        ("SSLError", HTTPStatus.SERVICE_UNAVAILABLE, "connection_error"),
        ("ProxyError", HTTPStatus.SERVICE_UNAVAILABLE, "connection_error"),
        ("InvalidHeader", HTTPStatus.BAD_REQUEST, "transport_error"),
        ("ValueError", HTTPStatus.BAD_REQUEST, "transport_error"),
    ],
)
def test_transport_errors_are_classified_by_class_name(
    name: str, expected_code: HTTPStatus, expected_kind: str
) -> None:
    exc = type(name, (Exception,), {})("boom")
    assert classify_transport_error(exc) == (expected_code, expected_kind)


def test_connect_timeout_is_a_timeout_not_a_connection_blip() -> None:
    """ConnectTimeout matches both name lists; timeout must win, because a retry cannot
    help a fixed 30s ceiling while it can help a transient blip."""
    code, kind = classify_transport_error(type("ConnectTimeout", (Exception,), {})("x"))
    assert (code, kind) == (HTTPStatus.REQUEST_TIMEOUT, "timeout")


def test_a_timeout_surfaces_as_408_with_a_named_cause() -> None:
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(  # type: ignore[method-assign]
        side_effect=type("ReadTimeout", (Exception,), {})("timed out after 30s")
    )

    response = client.request()

    assert response.code == HTTPStatus.REQUEST_TIMEOUT
    assert response.response.startswith("timeout:")


def test_a_connection_error_surfaces_as_503_so_it_gets_retried() -> None:
    """503 is >= 500, which is what makes the caller retry it. Under the old scheme this
    shared the 400 bucket with timeouts and was never retried."""
    client = ScribeLlmAnthropic(ScribeLlmSettings(api_key="k", model="m"))
    client.set_user_prompt(["hi"])
    client.http.post = MagicMock(  # type: ignore[method-assign]
        side_effect=type("ConnectionError", (Exception,), {})("reset by peer")
    )

    response = client.request()

    assert response.code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.response.startswith("connection_error:")
