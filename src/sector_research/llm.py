"""The model layer: a thin, resilient wrapper around the Anthropic SDK.

Everything that touches the network lives here so the agents stay pure and testable.
The wrapper exposes three call shapes the agents need:

* :meth:`LLMClient.complete_text` — free-form text with adaptive thinking.
* :meth:`LLMClient.complete_structured` — schema-validated output via ``parse``.
* :meth:`LLMClient.research` — a web-search turn that resolves ``pause_turn`` loops
  and returns the text plus the sources the model actually consulted.

Resilience is deliberate: the SDK already retries 429/5xx with backoff, and we layer
on top of it explicit refusal handling and safe web-search degradation, so a single
flaky tool call never takes down a whole report.
"""

from __future__ import annotations

import logging
from typing import TypeVar, cast

import anthropic
from anthropic.types import (
    Message,
    MessageParam,
    OutputConfigParam,
    ThinkingConfigAdaptiveParam,
    WebSearchTool20260209Param,
)
from pydantic import BaseModel

from .config import Settings
from .exceptions import ModelError, ModelRefusalError, StructuredOutputError
from .models import Source

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Adaptive thinking is the recommended mode on Opus 4.8; a module-level constant keeps
# every call site consistent and lets mypy match the SDK's typed overloads.
_THINKING: ThinkingConfigAdaptiveParam = {"type": "adaptive"}

# Bound the server-side tool loop so a run cannot spin forever on pause_turn.
_MAX_PAUSE_CONTINUATIONS = 5


class LLMClient:
    """A resilient facade over ``anthropic.Anthropic``.

    The underlying SDK client is created lazily on first use, so importing the package
    and running ``--help`` never require credentials. Inject a pre-built ``anthropic``
    client in tests to avoid any network access.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self._settings = settings
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        """The underlying SDK client, constructed on first access."""
        if self._client is None:
            self._client = anthropic.Anthropic(
                api_key=self._settings.require_api_key(),
                max_retries=self._settings.max_retries,
                timeout=self._settings.request_timeout_seconds,
            )
        return self._client

    @property
    def _output_config(self) -> OutputConfigParam:
        # ``effort`` is a str at rest (validated against a pattern in Settings); the
        # SDK types it as a Literal, so cast at this single boundary.
        return cast("OutputConfigParam", {"effort": self._settings.effort})

    # -- Free-form text ----------------------------------------------------------

    def complete_text(self, *, system: str, prompt: str) -> str:
        """Run a single adaptive-thinking turn and return the concatenated text."""
        try:
            response = self.client.messages.create(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens,
                system=system,
                thinking=_THINKING,
                output_config=self._output_config,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:  # already retried by the SDK
            raise ModelError(f"Text completion failed: {exc}") from exc

        _guard_refusal(response)
        return _extract_text(response)

    # -- Structured output -------------------------------------------------------

    def complete_structured(self, *, system: str, prompt: str, schema: type[T]) -> T:
        """Return output validated against ``schema`` using the parse helper."""
        try:
            response = self.client.messages.parse(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens,
                system=system,
                thinking=_THINKING,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
            )
        except anthropic.APIError as exc:
            raise ModelError(f"Structured completion failed: {exc}") from exc

        _guard_refusal(response)

        parsed = response.parsed_output
        if parsed is None:
            raise StructuredOutputError(
                f"Model did not return valid {schema.__name__}; stop_reason="
                f"{response.stop_reason}"
            )
        return parsed

    # -- Web research ------------------------------------------------------------

    def research(self, *, system: str, prompt: str) -> tuple[str, list[Source]]:
        """Run a web-search-enabled turn.

        Returns the model's synthesised text and the de-duplicated sources it
        consulted. If web search is disabled, this degrades gracefully to a plain
        text completion grounded in the model's own knowledge.
        """
        if not self._settings.enable_web_search:
            logger.info("Web search disabled; answering from model knowledge.")
            return self.complete_text(system=system, prompt=prompt), []

        tool: WebSearchTool20260209Param = {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": self._settings.max_web_searches,
        }
        messages: list[MessageParam] = [{"role": "user", "content": prompt}]

        try:
            response = self.client.messages.create(
                model=self._settings.model,
                max_tokens=self._settings.max_tokens,
                system=system,
                thinking=_THINKING,
                output_config=self._output_config,
                tools=[tool],
                messages=messages,
            )
            # Resolve any server-side tool loop that paused for continuation.
            continuations = 0
            while (
                response.stop_reason == "pause_turn"
                and continuations < _MAX_PAUSE_CONTINUATIONS
            ):
                assistant_turn = {"role": "assistant", "content": response.content}
                messages.append(cast("MessageParam", assistant_turn))
                response = self.client.messages.create(
                    model=self._settings.model,
                    max_tokens=self._settings.max_tokens,
                    system=system,
                    thinking=_THINKING,
                    output_config=self._output_config,
                    tools=[tool],
                    messages=messages,
                )
                continuations += 1
        except anthropic.APIError as exc:
            raise ModelError(f"Research turn failed: {exc}") from exc

        _guard_refusal(response)
        return _extract_text(response), _extract_sources(response)


def _guard_refusal(response: Message) -> None:
    """Raise a typed error if the model refused, before any content is read."""
    if response.stop_reason == "refusal":
        category = getattr(getattr(response, "stop_details", None), "category", None)
        raise ModelRefusalError(
            "The model declined this request on safety grounds.",
            category=category,
        )


def _extract_text(response: Message) -> str:
    """Join every text block in a response into one string."""
    parts = [block.text for block in response.content if block.type == "text"]
    text = "\n".join(part for part in parts if part).strip()
    if not text:
        raise ModelError("Model returned an empty response.")
    return text


def _extract_sources(response: Message) -> list[Source]:
    """Pull the web-search results the model consulted, de-duplicated by URL.

    Server-tool errors are returned as result blocks (HTTP 200), not exceptions, so
    a failed search yields no sources rather than crashing the run.
    """
    sources: list[Source] = []
    seen: set[str] = set()
    for block in response.content:
        if getattr(block, "type", None) != "web_search_tool_result":
            continue
        content = getattr(block, "content", None)
        # An error block has an object content; a success has a list of results.
        if not isinstance(content, list):
            logger.warning("Web search returned an error block; skipping.")
            continue
        for result in content:
            url = getattr(result, "url", None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(Source(title=getattr(result, "title", None) or url, url=url))
    return sources
