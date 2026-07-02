"""Tests for the resilient model layer, using fake SDK responses (no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from sector_research.config import Settings
from sector_research.exceptions import (
    ConfigurationError,
    ModelRefusalError,
    StructuredOutputError,
)
from sector_research.llm import (
    LLMClient,
    _extract_sources,
    _extract_text,
    _guard_refusal,
)
from sector_research.models import ResearchPlan


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _message(**kwargs) -> SimpleNamespace:
    kwargs.setdefault("stop_reason", "end_turn")
    kwargs.setdefault("stop_details", None)
    return SimpleNamespace(**kwargs)


def test_require_api_key_raises_when_missing():
    settings = Settings(anthropic_api_key=None)
    with pytest.raises(ConfigurationError):
        settings.require_api_key()


def test_extract_text_joins_blocks():
    msg = _message(content=[_text_block("hello"), _text_block("world")])
    assert _extract_text(msg) == "hello\nworld"


def test_extract_sources_dedupes_by_url():
    result_block = SimpleNamespace(
        type="web_search_tool_result",
        content=[
            SimpleNamespace(url="https://a.com", title="A"),
            SimpleNamespace(url="https://a.com", title="A duplicate"),
            SimpleNamespace(url="https://b.com", title="B"),
        ],
    )
    sources = _extract_sources(_message(content=[result_block]))
    assert [s.url for s in sources] == ["https://a.com", "https://b.com"]


def test_extract_sources_skips_error_blocks():
    error_block = SimpleNamespace(
        type="web_search_tool_result",
        content=SimpleNamespace(error_code="max_uses_exceeded"),  # object, not list
    )
    assert _extract_sources(_message(content=[error_block])) == []


def test_guard_refusal_raises_with_category():
    refusal = _message(
        stop_reason="refusal",
        stop_details=SimpleNamespace(category="cyber"),
        content=[],
    )
    with pytest.raises(ModelRefusalError) as exc:
        _guard_refusal(refusal)
    assert exc.value.category == "cyber"


def test_complete_structured_returns_parsed_output():
    plan = ResearchPlan(sector="x", objective="o", questions=[])
    fake_sdk = SimpleNamespace(
        messages=SimpleNamespace(
            parse=lambda **_: _message(parsed_output=plan, content=[_text_block("x")])
        )
    )
    client = LLMClient(Settings(anthropic_api_key="k"), client=fake_sdk)
    result = client.complete_structured(system="s", prompt="p", schema=ResearchPlan)
    assert result is plan


def test_complete_structured_raises_when_parse_fails():
    fake_sdk = SimpleNamespace(
        messages=SimpleNamespace(
            parse=lambda **_: _message(parsed_output=None, content=[])
        )
    )
    client = LLMClient(Settings(anthropic_api_key="k"), client=fake_sdk)
    with pytest.raises(StructuredOutputError):
        client.complete_structured(system="s", prompt="p", schema=ResearchPlan)


def test_research_degrades_to_text_when_web_disabled():
    settings = Settings(anthropic_api_key="k", enable_web_search=False)
    fake_sdk = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **_: _message(content=[_text_block("from knowledge")])
        )
    )
    client = LLMClient(settings, client=fake_sdk)
    text, sources = client.research(system="s", prompt="p")
    assert text == "from knowledge"
    assert sources == []
