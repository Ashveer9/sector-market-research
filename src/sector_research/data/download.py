"""Download the raw Online Retail II workbook from the UCI repository."""
from __future__ import annotations

import urllib.request
from pathlib import Path

from ..config import Config, get_logger, load_config

logger = get_logger(__name__)


def download_raw(cfg: Config | None = None, force: bool = False) -> Path:
    """Download the raw dataset if it is not already present.

    Parameters
    ----------
    cfg:
        Loaded :class:`Config`. Loaded from default location when ``None``.
    force:
        Re-download even if the file already exists.

    Returns
    -------
    Path to the downloaded ``.xlsx`` file.
    """
    cfg = cfg or load_config()
    url = cfg["data"]["source_url"]
    dest = cfg.path(cfg["data"]["raw_path"])
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and not force:
        logger.info("Raw data already present at %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
        return dest

    logger.info("Downloading raw data from %s", url)
    urllib.request.urlretrieve(url, dest)  # noqa: S310 — trusted UCI URL from config
    logger.info("Saved raw data to %s (%.1f MB)", dest, dest.stat().st_size / 1e6)
    return dest


if __name__ == "__main__":
    download_raw()
