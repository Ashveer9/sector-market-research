"""Structured data contracts shared between agents.

These Pydantic models are the typed hand-offs in the pipeline: the planner emits a
:class:`ResearchPlan`, the researcher fills :class:`ResearchFinding` objects, the
analyst produces a :class:`SectorAnalysis`, and the critic returns a
:class:`Critique`. Modelling each boundary explicitly is what lets the agents be
developed, validated, and tested in isolation.

Note: structured-output JSON Schema does not support numeric/length constraints, so
bounds (e.g. confidence in 0..1) are enforced post-hoc in application code and tests
rather than via ``Field(ge=..., le=...)`` on the model the API sees.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Confidence(StrEnum):
    """Qualitative confidence in a finding, used when a numeric score is overkill."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ResearchQuestion(BaseModel):
    """A single, answerable question the team must investigate."""

    topic: str = Field(description="The specific question to research.")
    rationale: str = Field(description="Why this question matters for the report.")


class ResearchPlan(BaseModel):
    """The planner's decomposition of a sector into concrete research questions."""

    sector: str = Field(description="The sector or market under study.")
    objective: str = Field(description="What a reader should learn from the report.")
    questions: list[ResearchQuestion] = Field(
        description="Ordered list of questions to investigate."
    )


class Source(BaseModel):
    """A citation backing a research finding."""

    title: str
    url: str


class ResearchFinding(BaseModel):
    """An answer to one research question, with provenance and a confidence flag."""

    topic: str
    summary: str
    sources: list[Source] = Field(default_factory=list)
    confidence: Confidence = Confidence.MEDIUM


class SwotAnalysis(BaseModel):
    """Classic SWOT decomposition."""

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    opportunities: list[str] = Field(default_factory=list)
    threats: list[str] = Field(default_factory=list)


class Competitor(BaseModel):
    """A notable player in the sector."""

    name: str
    positioning: str = Field(description="One line on how they compete.")


class SectorAnalysis(BaseModel):
    """The analyst's synthesis of the findings into a structured market view."""

    overview: str
    market_size: str = Field(description="Size / growth, with a caveat if estimated.")
    key_trends: list[str] = Field(default_factory=list)
    competitors: list[Competitor] = Field(default_factory=list)
    swot: SwotAnalysis = Field(default_factory=SwotAnalysis)
    opportunities: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class CritiqueIssue(BaseModel):
    """A single gap or weakness the critic found in a draft."""

    severity: Confidence = Field(description="How much this issue hurts the draft.")
    description: str
    suggestion: str = Field(description="A concrete way to address the issue.")


class Critique(BaseModel):
    """The critic's verdict on a draft analysis — the heart of the quality gate.

    ``completeness_score`` (0..1) drives the self-correction loop: a draft scoring
    below the configured threshold is sent back to the synthesizer for revision.
    """

    completeness_score: float = Field(
        description="Overall quality from 0.0 (unusable) to 1.0 (publication-ready)."
    )
    issues: list[CritiqueIssue] = Field(default_factory=list)
    verdict: str = Field(description="One-sentence overall assessment.")


class ExecutiveSummary(BaseModel):
    """The synthesizer's decision-maker-facing distillation of the analysis."""

    headline: str = Field(description="One-line takeaway a busy executive would keep.")
    key_takeaways: list[str] = Field(default_factory=list)
    recommendation: str = Field(description="The single recommended next action.")


class ReportMetadata(BaseModel):
    """Provenance for a finished report — what was asked, by what, and when."""

    sector: str
    model: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    revisions: int = 0
    final_score: float | None = None


class MarketResearchReport(BaseModel):
    """The complete deliverable: plan, evidence, analysis, and quality record."""

    metadata: ReportMetadata
    executive_summary: ExecutiveSummary
    plan: ResearchPlan
    findings: list[ResearchFinding]
    analysis: SectorAnalysis
    critique: Critique
