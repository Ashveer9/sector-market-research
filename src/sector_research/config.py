"""Configuration loading and logging helpers.

Centralises access to ``config/config.yaml`` so every module reads the same
settings, and provides a consistently formatted logger for the pipeline.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

# Repository root resolved relative to this file: src/sector_research/config.py
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


class Config:
    """Thin wrapper around the YAML config with attribute/dict access and
    convenient path resolution relative to the project root."""

    def __init__(self, data: dict[str, Any], root: Path = PROJECT_ROOT) -> None:
        self._data = data
        self.root = root

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def path(self, relative: str) -> Path:
        """Resolve a config-relative path against the project root."""
        return (self.root / relative).resolve()

    @property
    def random_state(self) -> int:
        return int(self._data["project"]["random_state"])


def load_config(path: str | Path | None = None) -> Config:
    """Load the project configuration from YAML."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    with open(cfg_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return Config(data)


def get_logger(name: str = "sector_research") -> logging.Logger:
    """Return a module logger with a single stream handler attached."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
