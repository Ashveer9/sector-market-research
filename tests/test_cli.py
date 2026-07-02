"""Tests for the CLI surface: argument parsing, exit codes, output routing."""

from __future__ import annotations

import json

from sector_research import cli
from sector_research.exceptions import ConfigurationError, ModelRefusalError


def _install_fake_run(monkeypatch, report=None, error=None):
    """Patch the orchestrator so the CLI runs without any model calls."""

    class FakeOrchestrator:
        def __init__(self, settings):
            self.settings = settings

        def run(self, sector, *, on_progress=None):
            if error is not None:
                raise error
            return report

    monkeypatch.setattr(cli, "ResearchOrchestrator", FakeOrchestrator)


def _build_report(sample_plan, sample_analysis, high_critique, sample_summary):
    from sector_research.models import MarketResearchReport, ReportMetadata

    return MarketResearchReport(
        metadata=ReportMetadata(
            sector="electric vehicles", model="claude-opus-4-8", final_score=0.9
        ),
        executive_summary=sample_summary,
        plan=sample_plan,
        findings=[],
        analysis=sample_analysis,
        critique=high_critique,
    )


def test_config_error_exits_with_code_2(monkeypatch, capsys):
    _install_fake_run(monkeypatch, error=ConfigurationError("no key"))
    code = cli.main(["some sector", "--quiet"])
    assert code == cli.EXIT_CONFIG
    assert "Configuration error" in capsys.readouterr().err


def test_refusal_exits_with_code_3(monkeypatch, capsys):
    _install_fake_run(
        monkeypatch, error=ModelRefusalError("declined", category="cyber")
    )
    code = cli.main(["some sector", "--quiet"])
    assert code == cli.EXIT_REFUSAL
    assert "cyber" in capsys.readouterr().err


def test_markdown_written_to_stdout(
    monkeypatch, capsys, sample_plan, sample_analysis, high_critique, sample_summary
):
    report = _build_report(sample_plan, sample_analysis, high_critique, sample_summary)
    _install_fake_run(monkeypatch, report=report)
    code = cli.main(["electric vehicles", "--quiet"])
    assert code == cli.EXIT_OK
    assert "# Market Research Report" in capsys.readouterr().out


def test_json_output_to_file(
    monkeypatch, tmp_path, sample_plan, sample_analysis, high_critique, sample_summary
):
    report = _build_report(sample_plan, sample_analysis, high_critique, sample_summary)
    _install_fake_run(monkeypatch, report=report)
    out = tmp_path / "report.json"
    code = cli.main(["electric vehicles", "-o", str(out), "--quiet"])
    assert code == cli.EXIT_OK
    payload = json.loads(out.read_text())
    assert payload["metadata"]["sector"] == "electric vehicles"


def test_no_web_flag_disables_search(
    monkeypatch, capsys, sample_plan, sample_analysis, high_critique, sample_summary
):
    captured = {}

    class FakeOrchestrator:
        def __init__(self, settings):
            captured["enable_web_search"] = settings.enable_web_search

        def run(self, sector, *, on_progress=None):
            return _build_report(
                sample_plan, sample_analysis, high_critique, sample_summary
            )

    monkeypatch.setattr(cli, "ResearchOrchestrator", FakeOrchestrator)
    cli.main(["electric vehicles", "--no-web", "--quiet"])
    assert captured["enable_web_search"] is False
