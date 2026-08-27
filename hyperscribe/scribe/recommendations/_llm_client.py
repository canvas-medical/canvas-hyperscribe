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
from typing import Any

from canvas_sdk.clients.llms.libraries import LlmAnthropic
from canvas_sdk.clients.llms.structures.llm_response import LlmResponse
from canvas_sdk.clients.llms.structures.settings.llm_settings import LlmSettings

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_EFFORT = "medium"
VALID_EFFORTS = ("low", "medium", "high", "xhigh", "max")

# Anthropic's ephemeral cache has a 5 minute TTL measured from the start of the request
# that writes it. Every chunk of a fill starts well inside that window, so the default
# TTL is the right one and the 2x write price of the 1h TTL would not pay for itself.
CACHE_CONTROL = {"type": "ephemeral"}


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
        """Delegate to the SDK, capturing the raw ``usage`` block on the way past.

        Done by shadowing ``self.http.post`` with a wrapper for the duration of the
        call rather than by reimplementing ``request``, so the SDK keeps owning
        response parsing and error handling and this stays a pure addition.
        """
        self.last_usage = {}
        # Restore exactly what was there. A blanket ``del`` would also remove a
        # pre-existing instance attribute (a test double, a decorated transport) rather
        # than only this wrapper.
        missing = object()
        previous = self.http.__dict__.get("post", missing)
        original_post = self.http.post

        def capturing_post(*args: Any, **kwargs: Any) -> Any:
            response = original_post(*args, **kwargs)
            try:
                if response.status_code == 200:
                    self.last_usage = json.loads(response.text).get("usage") or {}
            except (ValueError, TypeError, AttributeError):
                # Telemetry only. A malformed body is the SDK's problem to report.
                pass
            return response

        self.http.post = capturing_post
        try:
            return super().request()
        finally:
            if previous is missing:
                self.http.__dict__.pop("post", None)
            else:
                self.http.post = previous


def make_fill_client(
    api_key: str,
    model: str = DEFAULT_MODEL,
    effort: str = DEFAULT_EFFORT,
    cache_index: int | None = None,
) -> ScribeLlmAnthropic:
    """Build the client used by the questionnaire fill."""
    settings = ScribeLlmSettings(api_key=api_key, model=model or DEFAULT_MODEL, effort=effort)
    return ScribeLlmAnthropic(settings, cache_index=cache_index)
