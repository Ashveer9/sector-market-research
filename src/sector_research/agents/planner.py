"""The planner agent — turns a sector prompt into a concrete research plan."""

from __future__ import annotations

from ..llm import LLMClient
from ..models import ResearchPlan

_SYSTEM = """\
You are a senior market-research lead scoping a new engagement. Given a sector, you
decompose it into a small set of sharp, answerable research questions that together
cover market size, demand drivers, the competitive landscape, key trends, and risks.

Prefer 5-7 questions. Each must be specific enough to research directly and each must
earn its place — no filler. State the objective as the single insight a decision-maker
should walk away with.
"""


class PlannerAgent:
    """Decomposes a sector into a :class:`ResearchPlan` of research questions."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def plan(self, sector: str) -> ResearchPlan:
        """Produce a research plan for ``sector``."""
        prompt = (
            f"Sector to research: {sector}\n\n"
            "Produce a research plan: an objective and the ordered questions the "
            "team should investigate to write a decision-grade market report."
        )
        plan = self._llm.complete_structured(
            system=_SYSTEM, prompt=prompt, schema=ResearchPlan
        )
        # The model occasionally restates the sector loosely; normalise it so the
        # rest of the pipeline and the report metadata agree on one label.
        plan.sector = sector
        return plan
