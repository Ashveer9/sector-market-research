"""Render a :class:`MarketResearchReport` to Markdown.

Kept separate from the data model so the same report can be serialised as JSON (for
machines) or rendered as Markdown (for humans) without the model knowing about either.
"""

from __future__ import annotations

from .models import MarketResearchReport


def render_markdown(report: MarketResearchReport) -> str:
    """Render a full report as a self-contained Markdown document."""
    a = report.analysis
    s = report.executive_summary
    m = report.metadata
    lines: list[str] = []

    lines.append(f"# Market Research Report: {m.sector}")
    lines.append("")
    meta = (
        f"Generated {m.generated_at:%Y-%m-%d %H:%M UTC} · model `{m.model}` · "
        f"{m.revisions} revision(s)"
    )
    if m.final_score is not None:
        meta += f" · quality {m.final_score:.2f}"
    lines.append(f"_{meta}_")
    lines.append("")

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(f"**{s.headline}**")
    lines.append("")
    for takeaway in s.key_takeaways:
        lines.append(f"- {takeaway}")
    lines.append("")
    lines.append(f"**Recommendation:** {s.recommendation}")
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append(a.overview)
    lines.append("")
    lines.append(f"**Market size & growth:** {a.market_size}")
    lines.append("")

    _bullet_section(lines, "Key Trends", a.key_trends)

    if a.competitors:
        lines.append("## Competitive Landscape")
        lines.append("")
        for c in a.competitors:
            lines.append(f"- **{c.name}** — {c.positioning}")
        lines.append("")

    lines.append("## SWOT")
    lines.append("")
    _swot_quadrant(lines, "Strengths", a.swot.strengths)
    _swot_quadrant(lines, "Weaknesses", a.swot.weaknesses)
    _swot_quadrant(lines, "Opportunities", a.swot.opportunities)
    _swot_quadrant(lines, "Threats", a.swot.threats)

    _bullet_section(lines, "Opportunities", a.opportunities)
    _bullet_section(lines, "Risks", a.risks)

    lines.append("## Research Appendix")
    lines.append("")
    lines.append(f"_Objective: {report.plan.objective}_")
    lines.append("")
    for finding in report.findings:
        lines.append(f"### {finding.topic}")
        lines.append("")
        lines.append(f"_Confidence: {finding.confidence.value}_")
        lines.append("")
        lines.append(finding.summary)
        lines.append("")
        if finding.sources:
            lines.append("**Sources:**")
            for src in finding.sources:
                lines.append(f"- [{src.title}]({src.url})")
            lines.append("")

    lines.append("## Quality Assurance")
    lines.append("")
    lines.append(f"_{report.critique.verdict}_")
    lines.append("")
    lines.append(f"Completeness score: **{report.critique.completeness_score:.2f}**")
    lines.append("")
    if report.critique.issues:
        lines.append("Outstanding notes from the review:")
        for issue in report.critique.issues:
            lines.append(f"- _[{issue.severity.value}]_ {issue.description}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _bullet_section(lines: list[str], title: str, items: list[str]) -> None:
    if not items:
        return
    lines.append(f"## {title}")
    lines.append("")
    for item in items:
        lines.append(f"- {item}")
    lines.append("")


def _swot_quadrant(lines: list[str], title: str, items: list[str]) -> None:
    lines.append(f"### {title}")
    lines.append("")
    if items:
        for item in items:
            lines.append(f"- {item}")
    else:
        lines.append("_None identified._")
    lines.append("")
