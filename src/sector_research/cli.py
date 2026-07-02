"""Command-line interface.

Thin by design: parse arguments, wire up the orchestrator, render output, translate
typed exceptions into clean exit codes. All real work lives in the library so the CLI
stays a shell you could swap for a web service without touching the pipeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import __version__
from .config import load_settings
from .exceptions import ConfigurationError, ModelRefusalError, SectorResearchError
from .orchestrator import ProgressCallback, ResearchOrchestrator
from .report import render_markdown

# Exit codes: 0 ok, 1 unexpected, 2 configuration, 3 model refusal.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG = 2
EXIT_REFUSAL = 3


def build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser."""
    parser = argparse.ArgumentParser(
        prog="sector-research",
        description=(
            "Generate a source-backed market-research report for a sector using a "
            "self-correcting team of Claude agents."
        ),
    )
    parser.add_argument("sector", help="The sector or market to research.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write the report here (extension picks the format). Default: stdout.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format when writing to stdout. Default: markdown.",
    )
    parser.add_argument(
        "--no-web",
        action="store_true",
        help="Disable web search; research from model knowledge only.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output on stderr.",
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def _make_progress(quiet: bool) -> ProgressCallback | None:
    """Return a progress callback that writes to stderr unless quiet."""
    if quiet:
        return None

    def progress(stage: str, detail: str) -> None:
        print(f"  [{stage:>9}] {detail}", file=sys.stderr, flush=True)

    return progress


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    settings = load_settings()
    if args.no_web:
        settings.enable_web_search = False

    fmt = _format_for(args)

    try:
        orchestrator = ResearchOrchestrator(settings)
        report = orchestrator.run(args.sector, on_progress=_make_progress(args.quiet))
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    except ModelRefusalError as exc:
        detail = f" (category: {exc.category})" if exc.category else ""
        print(f"Request declined by the model{detail}: {exc}", file=sys.stderr)
        return EXIT_REFUSAL
    except SectorResearchError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    rendered = (
        json.dumps(report.model_dump(mode="json"), indent=2)
        if fmt == "json"
        else render_markdown(report)
    )

    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
        if not args.quiet:
            print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(rendered)

    return EXIT_OK


def _format_for(args: argparse.Namespace) -> str:
    """Resolve the output format from the extension or the --format flag."""
    if args.output is not None:
        suffix = args.output.suffix.lower()
        if suffix == ".json":
            return "json"
        if suffix in (".md", ".markdown"):
            return "markdown"
    return str(args.format)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
