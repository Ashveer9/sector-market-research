"""The orchestrator — the one component that knows the shape of the pipeline.

It wires the agents together and, crucially, owns the *self-correcting quality gate*:
the analyst drafts, the critic scores, and while the score is below the configured
threshold and revisions remain, the draft is sent back for a targeted rewrite. This is
the "system that fixes itself" — quality is enforced by the pipeline, not assumed.

Progress is reported through an optional callback so the CLI can render live status
without the orchestrator depending on any particular UI.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from .agents import (
    AnalystAgent,
    CriticAgent,
    PlannerAgent,
    ResearcherAgent,
    SynthesizerAgent,
)
from .config import Settings
from .llm import LLMClient
from .models import (
    Critique,
    MarketResearchReport,
    ReportMetadata,
    ResearchFinding,
    ResearchPlan,
    SectorAnalysis,
)

logger = logging.getLogger(__name__)

# A no-argument-constrained progress hook: stage label + human-readable detail.
ProgressCallback = Callable[[str, str], None]


def _noop(stage: str, detail: str) -> None:  # pragma: no cover - trivial default
    logger.info("[%s] %s", stage, detail)


class ResearchOrchestrator:
    """Coordinates the agent team into a single market-research report."""

    def __init__(
        self,
        settings: Settings,
        *,
        llm: LLMClient | None = None,
    ) -> None:
        self._settings = settings
        llm = llm or LLMClient(settings)
        self._planner = PlannerAgent(llm)
        self._researcher = ResearcherAgent(llm)
        self._analyst = AnalystAgent(llm)
        self._critic = CriticAgent(llm)
        self._synthesizer = SynthesizerAgent(llm)

    def run(
        self, sector: str, *, on_progress: ProgressCallback | None = None
    ) -> MarketResearchReport:
        """Produce a complete report for ``sector``.

        The pipeline is: plan -> research each question -> analyse -> (critique ->
        revise)* -> summarise -> assemble.
        """
        progress = on_progress or _noop

        progress("plan", f"Scoping research for '{sector}'")
        plan = self._planner.plan(sector)
        progress("plan", f"{len(plan.questions)} research questions identified")

        findings = []
        for index, question in enumerate(plan.questions, start=1):
            progress(
                "research",
                f"Investigating {index}/{len(plan.questions)}: {question.topic}",
            )
            findings.append(self._researcher.investigate(question))

        progress("analyse", "Synthesising findings into a structured analysis")
        analysis = self._analyst.analyse(plan, findings)

        analysis, critique, revisions = self._quality_gate(
            plan, findings, analysis, progress
        )

        progress("summarise", "Writing the executive summary")
        summary = self._synthesizer.summarise(analysis)

        progress("done", f"Report complete after {revisions} revision(s)")
        return MarketResearchReport(
            metadata=ReportMetadata(
                sector=sector,
                model=self._settings.model,
                revisions=revisions,
                final_score=critique.completeness_score,
            ),
            executive_summary=summary,
            plan=plan,
            findings=findings,
            analysis=analysis,
            critique=critique,
        )

    def _quality_gate(
        self,
        plan: ResearchPlan,
        findings: list[ResearchFinding],
        analysis: SectorAnalysis,
        progress: ProgressCallback,
    ) -> tuple[SectorAnalysis, Critique, int]:
        """Run critique-and-revise until the draft passes or revisions run out.

        Returns the accepted analysis, its critique, and the number of revisions used.
        """
        threshold = self._settings.quality_threshold
        revisions = 0

        critique = self._critic.review(analysis, findings)
        progress(
            "critique",
            f"Draft scored {critique.completeness_score:.2f} "
            f"(threshold {threshold:.2f})",
        )

        while (
            critique.completeness_score < threshold
            and revisions < self._settings.max_revisions
        ):
            revisions += 1
            progress("revise", f"Revision {revisions}: addressing critique")
            analysis = self._analyst.analyse(
                plan, findings, prior=analysis, critique=critique
            )
            critique = self._critic.review(analysis, findings)
            progress(
                "critique",
                f"Revision {revisions} scored {critique.completeness_score:.2f}",
            )

        return analysis, critique, revisions
