"""Tests for the data models and their serialisation round-trips."""

from __future__ import annotations

from sector_research.models import (
    Confidence,
    MarketResearchReport,
    ReportMetadata,
)


def test_report_round_trips_through_json(
    sample_plan, sample_analysis, high_critique, sample_summary
):
    report = MarketResearchReport(
        metadata=ReportMetadata(
            sector="electric vehicles",
            model="claude-opus-4-8",
            revisions=1,
            final_score=0.9,
        ),
        executive_summary=sample_summary,
        plan=sample_plan,
        findings=[],
        analysis=sample_analysis,
        critique=high_critique,
    )

    dumped = report.model_dump(mode="json")
    restored = MarketResearchReport.model_validate(dumped)

    assert restored.metadata.sector == "electric vehicles"
    assert restored.analysis.competitors[0].name == "Acme EV"
    assert restored.executive_summary.headline == sample_summary.headline


def test_metadata_defaults_to_utc_now():
    meta = ReportMetadata(sector="x", model="claude-opus-4-8")
    assert meta.generated_at.tzinfo is not None
    assert meta.revisions == 0


def test_confidence_is_ordered_enum():
    assert Confidence("high") is Confidence.HIGH
