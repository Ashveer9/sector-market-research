"""Typed exceptions for the sector-research pipeline.

A small, explicit exception hierarchy keeps failure handling legible: the CLI can
distinguish a configuration mistake (exit early, tell the user) from a transient
model failure (already retried) from a content-quality failure (degrade, don't crash).
"""

from __future__ import annotations


class SectorResearchError(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(SectorResearchError):
    """Raised when the runtime is misconfigured (e.g. missing API credentials)."""


class ModelError(SectorResearchError):
    """Raised when the model layer fails after exhausting its own retries."""


class ModelRefusalError(ModelError):
    """Raised when the model declines a request on safety grounds.

    Carries the structured refusal category when the API supplies one so callers
    can decide whether to surface it to the user or route to a fallback.
    """

    def __init__(self, message: str, *, category: str | None = None) -> None:
        super().__init__(message)
        self.category = category


class StructuredOutputError(ModelError):
    """Raised when the model could not return output matching the requested schema."""
