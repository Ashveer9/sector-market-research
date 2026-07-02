"""The analyst agent — synthesises findings into a structured market view."""

from __future__ import annotations

from ..llm import LLMClient
from ..models import Critique, ResearchFinding, ResearchPlan, SectorAnalysis

_SYSTEM = """\
You are a market-research analyst. You are given a set of researched findings and must
synthesise them into a coherent, structured analysis: overview, market size, key
trends, competitors, a SWOT, opportunities, and risks.

Ground every claim in the findings provided — do not invent facts the research does
not support. Where the evidence is weak, hedge honestly. Be specific and decision-
oriented; a reader should be able to act on this.
"""


class AnalystAgent:
    """Turns findings into a :class:`SectorAnalysis`, revising against critique."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def analyse(
        self,
        plan: ResearchPlan,
        findings: list[ResearchFinding],
        *,
        prior: SectorAnalysis | None = None,
        critique: Critique | None = None,
    ) -> SectorAnalysis:
        """Produce (or revise) a structured analysis.

        On the first pass ``prior`` and ``critique`` are ``None``. On a revision pass
        the previous draft and the critic's feedback are supplied, and the analyst is
        asked to address the specific issues rather than rewrite from scratch.
        """
        prompt = self._build_prompt(plan, findings, prior, critique)
        return self._llm.complete_structured(
            system=_SYSTEM, prompt=prompt, schema=SectorAnalysis
        )

    @staticmethod
    def _build_prompt(
        plan: ResearchPlan,
        findings: list[ResearchFinding],
        prior: SectorAnalysis | None,
        critique: Critique | None,
    ) -> str:
        findings_block = "\n\n".join(
            f"Q: {f.topic}\nConfidence: {f.confidence.value}\nFindings: {f.summary}"
            for f in findings
        )
        parts = [
            f"Sector: {plan.sector}",
            f"Objective: {plan.objective}",
            "",
            "Research findings:",
            findings_block,
        ]
        if prior is not None and critique is not None:
            issues = "\n".join(
                f"- [{i.severity.value}] {i.description} -> {i.suggestion}"
                for i in critique.issues
            )
            parts += [
                "",
                "A previous draft scored below the quality bar. Revise it to address "
                "the following issues specifically; keep what already works:",
                issues,
                "",
                "Previous draft (JSON):",
                prior.model_dump_json(indent=2),
            ]
        else:
            parts += [
                "",
                "Synthesise these into a structured market analysis.",
            ]
        return "\n".join(parts)
