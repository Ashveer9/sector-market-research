"""Shared fixtures and test doubles.

The whole design pays off here: every agent and the orchestrator accept an injected
model layer, so the entire pipeline can be exercised deterministically with zero
network access via :class:`FakeLLM`.
"""

from __future__ import annotations

from collections import defaultdict

import pytest

from sector_research.config import Settings
from sector_research.models import (
    Competitor,
    Confidence,
    Critique,
    CritiqueIssue,
    ExecutiveSummary,
    ResearchPlan,
    ResearchQuestion,
    SectorAnalysis,
    Source,
    SwotAnalysis,
)


class FakeLLM:
    """A schema-aware stand-in for :class:`~sector_research.llm.LLMClient`.

    Callers queue objects per schema type; each ``complete_structured`` call pops the
    next queued object for that schema. ``research`` returns canned text and sources.
    This lets tests script an entire run — including the critic scoring low then high
    to drive the revision loop — without touching the network.
    """

    def __init__(self) -> None:
        self._queues: dict[type, list] = defaultdict(list)
        self.research_calls: list[str] = []
        self.structured_calls: list[type] = []

    def queue(self, obj) -> None:
        self._queues[type(obj)].append(obj)

    def complete_structured(self, *, system: str, prompt: str, schema):
        self.structured_calls.append(schema)
        queue = self._queues[schema]
        if not queue:
            raise AssertionError(f"No queued {schema.__name__} for FakeLLM")
        return queue.pop(0)

    def complete_text(self, *, system: str, prompt: str) -> str:
        return "canned text answer"

    def research(self, *, system: str, prompt: str):
        self.research_calls.append(prompt)
        return (
            "A researched answer.",
            [Source(title="Example", url="https://example.com/report")],
        )


@pytest.fixture
def settings() -> Settings:
    """Settings with no real credentials and a tight loop for fast tests."""
    return Settings(
        anthropic_api_key="test-key",
        max_revisions=2,
        quality_threshold=0.8,
    )


@pytest.fixture
def sample_plan() -> ResearchPlan:
    return ResearchPlan(
        sector="electric vehicles",
        objective="Understand the EV market's trajectory.",
        questions=[
            ResearchQuestion(topic="Market size?", rationale="Sizing the opportunity."),
            ResearchQuestion(topic="Who competes?", rationale="Landscape."),
        ],
    )


@pytest.fixture
def sample_analysis() -> SectorAnalysis:
    return SectorAnalysis(
        overview="The EV market is growing fast.",
        market_size="~$500B, growing ~20% YoY (estimate).",
        key_trends=["Battery cost decline", "Charging build-out"],
        competitors=[Competitor(name="Acme EV", positioning="Premium segment")],
        swot=SwotAnalysis(strengths=["Brand"], threats=["Supply chain"]),
        opportunities=["Emerging markets"],
        risks=["Raw material volatility"],
    )


@pytest.fixture
def high_critique() -> Critique:
    return Critique(
        completeness_score=0.9,
        issues=[],
        verdict="Comprehensive and well-supported.",
    )


@pytest.fixture
def low_critique() -> Critique:
    return Critique(
        completeness_score=0.5,
        issues=[
            CritiqueIssue(
                severity=Confidence.HIGH,
                description="Market size lacks a source.",
                suggestion="Cite a named report.",
            )
        ],
        verdict="Promising but under-supported.",
    )


@pytest.fixture
def sample_summary() -> ExecutiveSummary:
    return ExecutiveSummary(
        headline="EVs are past the tipping point.",
        key_takeaways=["Demand is compounding", "Costs are falling"],
        recommendation="Invest in charging infrastructure.",
    )
