"""Tests for the orchestrator, focusing on the self-correcting quality gate."""

from __future__ import annotations

from sector_research.orchestrator import ResearchOrchestrator
from sector_research.report import render_markdown


def test_run_accepts_first_draft_when_it_passes(
    settings, sample_plan, sample_analysis, high_critique, sample_summary
):
    from .conftest import FakeLLM

    llm = FakeLLM()
    llm.queue(sample_plan)
    llm.queue(sample_analysis)
    llm.queue(high_critique)  # passes on first try
    llm.queue(sample_summary)

    report = ResearchOrchestrator(settings, llm=llm).run("electric vehicles")

    assert report.metadata.revisions == 0
    assert report.metadata.final_score == 0.9
    # One research call per question in the plan.
    assert len(llm.research_calls) == len(sample_plan.questions)


def test_run_revises_until_threshold_met(
    settings, sample_plan, sample_analysis, low_critique, high_critique, sample_summary
):
    from .conftest import FakeLLM

    llm = FakeLLM()
    llm.queue(sample_plan)
    llm.queue(sample_analysis)  # first draft
    llm.queue(low_critique)  # fails -> triggers a revision
    llm.queue(sample_analysis)  # revised draft
    llm.queue(high_critique)  # passes
    llm.queue(sample_summary)

    report = ResearchOrchestrator(settings, llm=llm).run("electric vehicles")

    assert report.metadata.revisions == 1
    assert report.metadata.final_score == 0.9


def test_run_stops_at_max_revisions(
    settings, sample_plan, sample_analysis, low_critique, sample_summary
):
    from .conftest import FakeLLM

    settings.max_revisions = 1
    llm = FakeLLM()
    llm.queue(sample_plan)
    llm.queue(sample_analysis)
    llm.queue(low_critique)  # draft fails
    llm.queue(sample_analysis)  # one revision (the cap)
    llm.queue(low_critique)  # still fails, but we're out of revisions
    llm.queue(sample_summary)

    report = ResearchOrchestrator(settings, llm=llm).run("electric vehicles")

    assert report.metadata.revisions == 1
    assert report.metadata.final_score == 0.5  # accepted despite being below bar


def test_progress_callback_receives_stages(
    settings, sample_plan, sample_analysis, high_critique, sample_summary
):
    from .conftest import FakeLLM

    llm = FakeLLM()
    for obj in (sample_plan, sample_analysis, high_critique, sample_summary):
        llm.queue(obj)

    stages: list[str] = []
    ResearchOrchestrator(settings, llm=llm).run(
        "electric vehicles", on_progress=lambda stage, _detail: stages.append(stage)
    )

    assert "plan" in stages
    assert "research" in stages
    assert "critique" in stages
    assert stages[-1] == "done"


def test_full_report_renders_to_markdown(
    settings, sample_plan, sample_analysis, high_critique, sample_summary
):
    from .conftest import FakeLLM

    llm = FakeLLM()
    for obj in (sample_plan, sample_analysis, high_critique, sample_summary):
        llm.queue(obj)

    report = ResearchOrchestrator(settings, llm=llm).run("electric vehicles")
    markdown = render_markdown(report)

    assert "# Market Research Report: electric vehicles" in markdown
    assert "## Executive Summary" in markdown
    assert "## SWOT" in markdown
    assert "## Research Appendix" in markdown
    assert "https://example.com/report" in markdown  # source from FakeLLM.research
