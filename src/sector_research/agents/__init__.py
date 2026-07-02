"""The specialist agents that make up the research team.

Each agent owns one responsibility and one prompt. They share the :class:`LLMClient`
but hold no other state, which keeps them independently testable and easy to reason
about — the orchestrator is the only component that knows the pipeline shape.
"""

from __future__ import annotations

from .analyst import AnalystAgent
from .critic import CriticAgent
from .planner import PlannerAgent
from .researcher import ResearcherAgent
from .synthesizer import SynthesizerAgent

__all__ = [
    "AnalystAgent",
    "CriticAgent",
    "PlannerAgent",
    "ResearcherAgent",
    "SynthesizerAgent",
]
