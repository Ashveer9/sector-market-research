"""Structured logging setup for the pipeline."""

import logging
import sys
from pathlib import Path
from typing import Optional

import yaml


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """Return a configured logger for the given module name."""
    config = _load_log_config()

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.get("level", "INFO")))

    if not logger.handlers:
        fmt = logging.Formatter(
            fmt=config.get("format", "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"),
            datefmt=config.get("date_format", "%Y-%m-%d %H:%M:%S"),
        )

        # Console handler
        ch = logging.StreamHandler(sys.stdout)
        ch.setFormatter(fmt)
        logger.addHandler(ch)

        # Optional file handler
        if log_file:
            Path(log_file).parent.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(log_file)
            fh.setFormatter(fmt)
            logger.addHandler(fh)

    return logger


def _load_log_config() -> dict:
    config_path = Path(__file__).parent.parent.parent / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
            return cfg.get("logging", {})
    return {}
