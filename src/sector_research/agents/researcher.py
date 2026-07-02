"""The researcher agent — answers each question with live web search."""

from __future__ import annotations

import logging

from ..llm import LLMClient
from ..models import Confidence, ResearchFinding, ResearchQuestion, Source

logger = logging.getLogger(__name__)

_SYSTEM = """\
You are a diligent research analyst. Answer the given question factually and
concisely, grounding claims in current sources found via web search. Lead with the
answer, then the supporting detail. If the evidence is thin or dated, say so plainly
rather than overstating confidence. Do not fabricate figures — attribute every number
to where it came from.
"""


class ResearcherAgent:
    """Answers each :class:`ResearchQuestion`, capturing sources and confidence.

    The researcher is deliberately fault-tolerant: one question failing to research
    must not sink the report, so failures degrade to a low-confidence placeholder
    finding and the pipeline continues.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def investigate(self, question: ResearchQuestion) -> ResearchFinding:
        """Research a single question into a :class:`ResearchFinding`."""
        prompt = (
            f"Research question: {question.topic}\n"
            f"Why it matters: {question.rationale}\n\n"
            "Search for current information and write a tight, sourced answer."
        )
        try:
            text, sources = self._llm.research(system=_SYSTEM, prompt=prompt)
        except Exception:  # degrade gracefully, never abort the whole report
            logger.exception("Research failed for question: %s", question.topic)
            return ResearchFinding(
                topic=question.topic,
                summary=(
                    "Research could not be completed for this question in this run."
                ),
                sources=[],
                confidence=Confidence.LOW,
            )

        return ResearchFinding(
            topic=question.topic,
            summary=text,
            sources=sources,
            confidence=_confidence_from_sources(sources),
        )


def _confidence_from_sources(sources: list[Source]) -> Confidence:
    """Heuristic: more corroborating sources -> higher confidence."""
    if len(sources) >= 3:
        return Confidence.HIGH
    if len(sources) >= 1:
        return Confidence.MEDIUM
    return Confidence.LOW
