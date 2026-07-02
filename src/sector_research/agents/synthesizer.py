"""The synthesizer agent — distils the final analysis for decision-makers."""

from __future__ import annotations

from ..llm import LLMClient
from ..models import ExecutiveSummary, SectorAnalysis

_SYSTEM = """\
You are a strategy partner writing the front page an executive actually reads. Given a
completed market analysis, distil it into a single headline, a handful of sharp key
takeaways, and one clear recommended next action. Say what matters and cut what
doesn't. No hedging theatre, no restating the whole analysis — just the decision-grade
essence.
"""


class SynthesizerAgent:
    """Produces the :class:`ExecutiveSummary` that tops the finished report."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def summarise(self, analysis: SectorAnalysis) -> ExecutiveSummary:
        """Distil ``analysis`` into an executive summary."""
        prompt = (
            "Write the executive summary for this market analysis.\n\n"
            f"Analysis (JSON):\n{analysis.model_dump_json(indent=2)}"
        )
        return self._llm.complete_structured(
            system=_SYSTEM, prompt=prompt, schema=ExecutiveSummary
        )
