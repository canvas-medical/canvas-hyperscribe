"""Anthropic client for the questionnaire fill, on a current-generation model.

The SDK's ``LlmSettingsAnthropic.to_dict`` always emits ``temperature``, and every
current-generation model rejects sampling parameters with a 400, so a plain
model-string swap is not enough — the request body has to be composed here.

Two other things this override buys:

* ``thinking`` and ``output_config.effort``, which the SDK settings dataclass has no
  field for. Forced ``tool_choice`` (how the SDK does structured output) is compatible
  with adaptive thinking on the Claude API; the disable-thinking requirement applies
  only to Amazon Bedrock, and this plugin posts directly to api.anthropic.com.
* ``cache_control`` on the transcript block. The fill sends the same transcript once per
  chunk, so without caching the chunking that keeps each request inside the SDK's 30s
  timeout would multiply the input cost by the chunk count.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.llm_response import LlmResponse
from canvas_sdk.clients.llms.structures.llm_tokens import LlmTokens
from canvas_sdk.clients.llms.structures.settings.llm_settings import LlmSettings

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")

# Anthropic's ephemeral cache has a 5 minute TTL measured from the start of the request
# that writes it. Every chunk of a fill starts well inside that window, so the default
# TTL is the right one and the 2x write price of the 1h TTL would not pay for itself.
CACHE_CONTROL = {"type": "ephemeral"}


# Failure kinds, used as a stable prefix on the response text so the cause is greppable in
# the logs and readable in the QUESTIONNAIRE_FILL_FAILED audit row.
FAILURE_TIMEOUT = "timeout"
FAILURE_CONNECTION = "connection_error"
FAILURE_TRANSPORT = "transport_error"
FAILURE_TRUNCATED = "truncated"

# Concrete `requests` exception class names. Classified by NAME rather than by `isinstance`
# because the sandbox's ALLOWED_MODULES exposes only a handful of names from `requests`
# (Session, post, RequestException, ...) and neither `Timeout` nor `ConnectionError` is
# among them, so they cannot be imported to catch.
_TIMEOUT_NAMES = ("ConnectTimeout", "ReadTimeout", "Timeout")
_CONNECTION_NAMES = ("ConnectionError", "SSLError", "ProxyError", "ChunkedEncodingError")


def classify_transport_error(exc: BaseException) -> tuple[HTTPStatus, str]:
    """Map a transport exception to a status that preserves its cause.

    A timeout becomes 408 and stays non-retryable: the 30s ceiling is fixed, so a retry
    burns another 30 seconds on the same too-large chunk. A connection error becomes 503,
    which the caller's ``code >= 500`` rule makes retryable — that is the case a single
    retry genuinely fixes, and it used to be dropped for sharing a bucket with timeouts.
    """
    # ``exc.__class__.__name__``, not ``type(exc).__name__``: `type` is NOT in the
    # sandbox's builtins, so the latter raises NameError at request time — invisible to
    # `canvas validate`, which only executes module-level code. Both of these dunders are
    # in the sandbox's read allowlist.
    name = exc.__class__.__name__
    # Timeout first: ConnectTimeout matches both lists and is a timeout, not a blip.
    if any(candidate in name for candidate in _TIMEOUT_NAMES):
        return HTTPStatus.REQUEST_TIMEOUT, FAILURE_TIMEOUT
    if name in _CONNECTION_NAMES:
        return HTTPStatus.SERVICE_UNAVAILABLE, FAILURE_CONNECTION
    return HTTPStatus.BAD_REQUEST, FAILURE_TRANSPORT


class ScribeLlmSettings(LlmSettings):
    """Settings for a current-generation Anthropic model.

    Deliberately does NOT extend ``LlmSettingsAnthropic``: that class requires a
    ``temperature`` and puts it in ``to_dict``, which is exactly what has to go.

    Written with an explicit ``__init__`` rather than ``@dataclass``, even though the
    SDK base class is one. ``dataclasses`` resolves field types via
    ``sys.modules.get(cls.__module__).__dict__``, and the plugin sandbox never registers
    its modules in ``sys.modules``, so decorating a class defined here raises
    ``AttributeError: 'NoneType' object has no attribute '__dict__'`` at import time.
    Subclassing a dataclass is fine; becoming one is not.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 8192,
        effort: str = DEFAULT_EFFORT,
    ) -> None:
        super().__init__(api_key=api_key, model=model)
        self.max_tokens = max_tokens
        self.effort = effort

    def to_dict(self) -> dict[str, Any]:
        """Request fields owned by the settings. Sampling params are intentionally absent."""
        effort = self.effort if self.effort in VALID_EFFORTS else DEFAULT_EFFORT
        return {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }


class ScribeLlmAnthropic(LlmAnthropic):
    """``LlmAnthropic`` with a cacheable prefix.

    ``cache_index`` is the position of the content block to mark as the end of the
    cached prefix. Blocks are built from the prompt turns in order, and
    ``LlmAnthropic.to_dict`` merges contiguous same-role turns into one message, so a
    caller that sets the system prompt then calls ``set_user_prompt`` twice produces
    blocks 0 (system), 1 (transcript) and 2 (chunk definition) inside a single user
    message. Marking block 1 caches the system prompt and transcript together and
    leaves the per-chunk definition out of the cached prefix, where it belongs.
    """

    def __init__(self, settings: LlmSettings, cache_index: int | None = None) -> None:
        super().__init__(settings)
        self.cache_index = cache_index
        # Raw ``usage`` from the last response. The SDK narrows it to prompt/generated
        # counts, which drops ``cache_read_input_tokens`` — the one number that says
        # whether the prefix caching this design depends on is actually working.
        self.last_usage: dict[str, Any] = {}
        # ``stop_reason`` from the last response. Anthropic drops the incomplete tool_use
        # arguments when generation is cut off at ``max_tokens``, so the block arrives with
        # an empty ``input``. That parses cleanly as "no items", which is indistinguishable
        # from the model deliberately abstaining on every question - the worst available
        # failure for a feature whose whole safety story is that abstention is meaningful.
        self.last_stop_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Compose the request body, stamping ``cache_control`` on the prefix block."""
        payload: dict[str, Any] = super().to_dict()
        if self.cache_index is None:
            return payload
        # Blocks are numbered across the whole request, not per message, because the
        # caller thinks in prompt turns and does not know how the SDK merged them.
        index = 0
        for message in payload.get("messages", []):
            for block in message.get("content", []):
                if index == self.cache_index and block.get("type") == "text":
                    block["cache_control"] = dict(CACHE_CONTROL)
                index += 1
        return payload

    def request(self) -> LlmResponse:
        """POST to Anthropic and parse the response.

        Reimplemented rather than delegating to ``super().request()``, for two reasons
        that both matter on a thinking model.

        The SDK reads structured output from ``content[0]``, which assumes the tool_use
        block is first. With thinking enabled the first block is a ``thinking`` block, so
        that lookup returns ``{}`` and every fill comes back empty. This selects the
        tool_use block by type instead.

        And the SDK discards everything in ``usage`` except the prompt and generated
        counts, which drops ``cache_read_input_tokens`` — the one number that says
        whether the prefix caching this design depends on is working. An earlier version
        captured it by shadowing ``self.http.post``, which the sandbox rejects: reading
        ``self.http.__dict__`` to restore the transport is blocked attribute access, and
        it 500s the request with no plugin log.
        """
        self.last_usage = {}
        self.last_stop_reason = ""
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": self.settings.api_key,
        }
        tokens = LlmTokens(prompt=0, generated=0)
        try:
            http_response = self.http.post("/v1/messages", headers=headers, data=json.dumps(self.to_dict()))
        except Exception as exc:
            # Give the transport failure its own status so the cause survives into the
            # logs. Collapsing everything into BAD_REQUEST made a 30s timeout — the
            # likeliest failure here, since a long transcript pushes chunk latency toward
            # the wall — read as "your request was malformed", pointing at the wrong fix.
            code, kind = classify_transport_error(exc)
            return LlmResponse(code=code, response=f"{kind}: {exc}", tokens=tokens)

        code = http_response.status_code
        if code != HTTPStatus.OK.value:
            return LlmResponse(code=HTTPStatus(code), response=http_response.text, tokens=tokens)

        try:
            body = json.loads(http_response.text)
        except (ValueError, TypeError):
            return LlmResponse(code=HTTPStatus.BAD_REQUEST, response=http_response.text, tokens=tokens)

        blocks = body.get("content") or []
        if self.schema:
            payload: dict[str, Any] = next((b.get("input", {}) for b in blocks if b.get("type") == "tool_use"), {})
            text = json.dumps(payload)
        else:
            text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")

        self.last_stop_reason = body.get("stop_reason") or ""
        self.last_usage = body.get("usage") or {}
        tokens = LlmTokens(
            prompt=self.last_usage.get("input_tokens") or 0,
            generated=self.last_usage.get("output_tokens") or 0,
        )
        return LlmResponse(code=HTTPStatus.OK, response=text, tokens=tokens)


def make_fill_client(
    api_key: str,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    cache_index: int | None = None,
) -> ScribeLlmAnthropic:
    """Build the client used by the questionnaire fill."""
    settings = ScribeLlmSettings(api_key=api_key, model=model or DEFAULT_MODEL, effort=effort)
    return ScribeLlmAnthropic(settings, cache_index=cache_index)
