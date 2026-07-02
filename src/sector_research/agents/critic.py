"""The critic agent — the quality gate that drives self-correction."""

from __future__ import annotations

from ..llm import LLMClient
from ..models import Critique, ResearchFinding, SectorAnalysis

_SYSTEM = """\
You are a rigorous review lead who signs off market-research deliverables. Assess the
draft analysis for completeness, evidential support, internal consistency, and
decision-usefulness. Reward specificity and honest hedging; penalise vague claims,
unsupported figures, and gaps against the research findings.

Score from 0.0 (unusable) to 1.0 (publication-ready). Report concrete, actionable
issues — each with a severity and a specific fix. Be exacting but fair: a solid,
well-supported draft with minor gaps should score around 0.8, not 0.95.
"""


class CriticAgent:
    """Scores a draft analysis and enumerates concrete issues to fix."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def review(
        self, analysis: SectorAnalysis, findings: list[ResearchFinding]
    ) -> Critique:
        """Return a :class:`Critique` of ``analysis`` against the ``findings``."""
        findings_block = "\n\n".join(
            f"Q: {f.topic}\nFindings: {f.summary}" for f in findings
        )
        prompt = (
            "Review this draft market analysis against the research it is built on.\n\n"
            f"Research findings:\n{findings_block}\n\n"
            f"Draft analysis (JSON):\n{analysis.model_dump_json(indent=2)}"
        )
        critique = self._llm.complete_structured(
            system=_SYSTEM, prompt=prompt, schema=Critique
        )
        # Clamp defensively: the schema can't enforce numeric bounds, so protect the
        # loop's threshold comparison from an out-of-range score.
        critique.completeness_score = _clamp(critique.completeness_score)
        return critique


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Constrain ``value`` to the ``[low, high]`` interval."""
    return max(low, min(high, value))
