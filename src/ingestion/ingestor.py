"""
Data ingestion layer: reads source CSV (Kaggle or local sample) and
emits a validated raw DataFrame ready for Bronze layer persistence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Canonical column names expected from the Global Superstore CSV
EXPECTED_COLUMNS = {
    "Row ID": "row_id",
    "Order ID": "order_id",
    "Order Date": "order_date",
    "Ship Date": "ship_date",
    "Ship Mode": "ship_mode",
    "Customer ID": "customer_id",
    "Customer Name": "customer_name",
    "Segment": "segment",
    "City": "city",
    "State": "state",
    "Country": "country",
    "Postal Code": "postal_code",
    "Market": "market",
    "Region": "region",
    "Product ID": "product_id",
    "Category": "category",
    "Sub-Category": "sub_category",
    "Product Name": "product_name",
    "Sales": "sales",
    "Quantity": "quantity",
    "Discount": "discount",
    "Profit": "profit",
    "Shipping Cost": "shipping_cost",
    "Order Priority": "order_priority",
}


@dataclass
class IngestionResult:
    source_path: str
    rows_read: int
    rows_after_schema_check: int
    columns_found: list[str]
    columns_missing: list[str]
    file_hash: str
    ingested_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    success: bool = True
    error: Optional[str] = None


class Ingestor:
    """Reads CSV source data and normalises column names."""

    def __init__(self, source_path: Optional[str] = None) -> None:
        self.source_path = Path(
            source_path or config.sample_path / "global_superstore.csv"
        )

    def ingest(self) -> tuple[pd.DataFrame, IngestionResult]:
        """Read source CSV and return a normalised DataFrame."""
        logger.info("Ingesting data from: %s", self.source_path)

        if not self.source_path.exists():
            raise FileNotFoundError(
                f"Source file not found: {self.source_path}. "
                "Run `python scripts/generate_sample_data.py` first."
            )

        file_hash = self._compute_hash(self.source_path)

        df = pd.read_csv(
            self.source_path,
            encoding="latin-1",
            low_memory=False,
            parse_dates=False,
        )

        rows_read = len(df)
        logger.info("Read %d rows, %d columns", rows_read, len(df.columns))

        df, found, missing = self._normalise_columns(df)

        result = IngestionResult(
            source_path=str(self.source_path),
            rows_read=rows_read,
            rows_after_schema_check=len(df),
            columns_found=found,
            columns_missing=missing,
            file_hash=file_hash,
            success=len(missing) == 0,
            error=f"Missing columns: {missing}" if missing else None,
        )

        if missing:
            logger.warning("Schema mismatch — missing columns: %s", missing)
        else:
            logger.info("Schema check passed. Ingestion complete.")

        self._write_manifest(result)
        return df, result

    def _normalise_columns(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[str], list[str]]:
        """Rename raw column names to snake_case canonical names."""
        rename_map = {
            col: EXPECTED_COLUMNS[col]
            for col in df.columns
            if col in EXPECTED_COLUMNS
        }
        df = df.rename(columns=rename_map)

        found = list(rename_map.values())
        expected_targets = list(EXPECTED_COLUMNS.values())
        missing = [c for c in expected_targets if c not in df.columns]

        return df, found, missing

    @staticmethod
    def _compute_hash(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    @staticmethod
    def _write_manifest(result: IngestionResult) -> None:
        manifest_dir = config.raw_path / "_manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = manifest_dir / f"ingestion_{ts}.json"
        with open(path, "w") as f:
            json.dump(result.__dict__, f, indent=2)
        logger.debug("Manifest written to %s", path)
