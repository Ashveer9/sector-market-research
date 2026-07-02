"""Runtime configuration.

Settings are read from the environment (and an optional ``.env`` file) so the same
code runs unchanged in local development, CI, and a container. Every value has a
sensible default except the API key, which is intentionally required at call time
rather than import time — importing the package must never fail.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings.

    Attributes mirror ``SECTOR_RESEARCH_*`` environment variables (plus the standard
    ``ANTHROPIC_API_KEY``). Validation happens once, at construction, so a bad value
    fails fast with a clear message instead of surfacing deep inside an API call.
    """

    model_config = SettingsConfigDict(
        env_prefix="SECTOR_RESEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Credentials — read from the conventional ANTHROPIC_API_KEY, not the prefixed name.
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")

    # Model selection. Opus 4.8 is the most capable model and the right default for
    # analyst-grade reasoning; override per-deployment via SECTOR_RESEARCH_MODEL.
    model: str = "claude-opus-4-8"
    effort: str = Field(default="high", pattern="^(low|medium|high|xhigh|max)$")

    # Token ceilings. Generous defaults; large outputs stream to avoid HTTP timeouts.
    max_tokens: int = Field(default=8000, ge=1024, le=128_000)

    # Resilience knobs for the model layer.
    max_retries: int = Field(default=4, ge=0, le=10)
    request_timeout_seconds: float = Field(default=600.0, gt=0)

    # Web research. The researcher uses the server-side web-search tool; cap usage so
    # a single run can't fan out unboundedly.
    enable_web_search: bool = True
    max_web_searches: int = Field(default=6, ge=1, le=20)

    # Self-correction loop. The critic scores each draft; if it scores below the
    # threshold and revisions remain, the synthesizer revises against the critique.
    quality_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_revisions: int = Field(default=2, ge=0, le=5)

    def require_api_key(self) -> str:
        """Return the API key or raise a clear configuration error.

        Called lazily, immediately before the first network request, so that unit
        tests and ``--help`` never need credentials.
        """
        if not self.anthropic_api_key:
            from .exceptions import ConfigurationError

            raise ConfigurationError(
                "No Anthropic API key found. Set ANTHROPIC_API_KEY in your "
                "environment or .env file."
            )
        return self.anthropic_api_key


def load_settings() -> Settings:
    """Construct :class:`Settings` from the current environment."""
    return Settings()
