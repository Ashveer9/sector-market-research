"""Tests for individual agents in isolation."""

from __future__ import annotations

from sector_research.agents import (
    AnalystAgent,
    CriticAgent,
    PlannerAgent,
    ResearcherAgent,
    SynthesizerAgent,
)
from sector_research.models import (
    Confidence,
    Critique,
    ResearchQuestion,
)


def test_planner_normalises_sector(sample_plan):
    fake = _FakeLLMFactory()
    # Planner echoes a loosely-worded sector; the agent must pin it back.
    sample_plan.sector = "EVs (loosely worded)"
    fake.queue(sample_plan)
    plan = PlannerAgent(fake).plan("electric vehicles")
    assert plan.sector == "electric vehicles"


def test_researcher_returns_finding_with_sources():
    fake = _FakeLLMFactory()
    finding = ResearcherAgent(fake).investigate(
        ResearchQuestion(topic="Market size?", rationale="Sizing.")
    )
    assert finding.topic == "Market size?"
    assert finding.sources
    assert finding.confidence == Confidence.MEDIUM  # one source -> medium


def test_researcher_degrades_on_failure():
    class Boom:
        def research(self, **_):
            raise RuntimeError("network down")

    finding = ResearcherAgent(Boom()).investigate(
        ResearchQuestion(topic="Q", rationale="R")
    )
    assert finding.confidence == Confidence.LOW
    assert finding.sources == []


def test_critic_clamps_out_of_range_score(sample_analysis):
    fake = _FakeLLMFactory()
    fake.queue(Critique(completeness_score=1.7, issues=[], verdict="over the top"))
    critique = CriticAgent(fake).review(analysis=sample_analysis, findings=[])
    assert critique.completeness_score == 1.0


def test_analyst_and_synthesizer_pass_through(
    sample_plan, sample_analysis, sample_summary
):
    fake = _FakeLLMFactory()
    fake.queue(sample_analysis)
    fake.queue(sample_summary)
    analysis = AnalystAgent(fake).analyse(plan=sample_plan, findings=[])
    summary = SynthesizerAgent(fake).summarise(sample_analysis)
    assert analysis is sample_analysis
    assert summary is sample_summary


class _FakeLLMFactory:
    """Minimal local double, keeping the agent tests self-contained."""

    def __init__(self) -> None:
        self._queue: list = []

    def queue(self, obj) -> None:
        self._queue.append(obj)

    def complete_structured(self, *, system, prompt, schema):
        return self._queue.pop(0)

    def complete_text(self, *, system, prompt):
        return "text"

    def research(self, *, system, prompt):
        from sector_research.models import Source

        return "answer", [Source(title="Example", url="https://example.com")]
