# Architecture & design notes

This document explains *why* the system is shaped the way it is. For a usage-level
overview see the [README](../README.md).

## The core idea: quality is enforced, not assumed

A naive "write me a market report" prompt produces one draft and hopes it's good. The
central design decision here is to make the pipeline **adversarial with itself**: a
separate critic agent scores every draft against the evidence, and the orchestrator
loops the analyst back to fix the specific gaps the critic names until the draft clears
a configurable bar (or runs out of revisions).

```
analyst.draft ─▶ critic.score ─┬─ score ≥ threshold ─▶ accept
                               └─ score < threshold & revisions left
                                     ▲                         │
                                     └── analyst.revise(critique) ◀┘
```

This is what makes the output trustworthy: the report ships with its own quality score
and the critic's outstanding notes attached, so a reader can see *how much* to trust it
rather than taking fluent prose at face value.

## Layering

The dependency direction is strictly one way, which keeps each layer independently
testable and replaceable:

```
cli → orchestrator → agents → llm → anthropic SDK
                        │        │
                        └──▶ models ◀──┘   (shared typed contracts)
        report ◀── models
```

- **`config`** — typed settings from the environment. Validated once, at construction.
- **`models`** — Pydantic contracts that are the *only* thing agents share. Changing a
  hand-off is a typed, greppable change.
- **`llm`** — the single seam that touches the network. Everything above it is pure.
- **`agents`** — one responsibility and one prompt each; hold no state beyond the client.
- **`orchestrator`** — the only component that knows the pipeline shape.
- **`report` / `cli`** — presentation and process concerns, swappable without touching
  the pipeline.

## Resilience decisions

| Failure | Handling | Rationale |
|---------|----------|-----------|
| Transient 429 / 5xx | SDK retry with backoff (`max_retries`) | Don't reinvent what the SDK does well. |
| A single research question fails | Degrade to a low-confidence placeholder finding | One bad search must not sink the whole report. |
| Web search returns an error block | Treated as "no sources" (returns HTTP 200, not an exception) | Server-tool errors are data, not exceptions. |
| Model safety refusal | Typed `ModelRefusalError` → CLI exit code 3 | Distinct, actionable outcome for the caller. |
| Schema mismatch | Typed `StructuredOutputError` | Fail loudly at the boundary, not deep in the pipeline. |
| Out-of-range critic score | Clamped to `[0, 1]` | The schema can't enforce numeric bounds, so the loop guards itself. |

## Testing strategy

The whole point of putting the network behind one injectable `LLMClient` is that the
entire pipeline — including the critique-and-revise loop — runs deterministically with
zero API calls. Tests queue canned agent outputs (e.g. critic scores low, then high) to
drive the orchestrator through every branch. See `tests/conftest.py`'s `FakeLLM`.

## Extension points

- **New agent / analysis dimension** — add a Pydantic model in `models.py`, an agent in
  `agents/`, and a step in the orchestrator. Nothing else needs to know.
- **Different surface (web service, queue worker)** — depend on `ResearchOrchestrator`
  directly; the CLI is just one caller.
- **Different output format** — add a renderer alongside `report.render_markdown`; the
  report model is presentation-agnostic.
- **Swap the model** — set `SECTOR_RESEARCH_MODEL`; the wrapper is model-agnostic.
