"""
Bronze layer: persists raw ingested data as Parquet files.
Data is written as-is — no transformations, partitioned by market.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BronzeWriter:
    """Writes raw DataFrames to the Bronze (raw) Parquet layer."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or config.raw_path
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, df: pd.DataFrame, dataset_name: str = "orders") -> Path:
        """
        Persist raw DataFrame as partitioned Parquet.

        Partitions by 'market' column if present; falls back to a single file.
        Adds pipeline metadata columns before writing.
        """
        logger.info(
            "Writing %d rows to Bronze layer (dataset=%s)", len(df), dataset_name
        )

        df = self._add_metadata(df)

        partition_cols = None
        if "market" in df.columns:
            # Ensure partition column is clean
            df["market"] = df["market"].fillna("UNKNOWN").str.strip().str.upper()
            partition_cols = ["market"]

        table = pa.Table.from_pandas(df, preserve_index=False)

        out_path = self.output_dir / dataset_name
        out_path.mkdir(parents=True, exist_ok=True)

        pq.write_to_dataset(
            table,
            root_path=str(out_path),
            partition_cols=partition_cols,
            compression=config.get("pipeline", "bronze_compression", default="snappy"),
            existing_data_behavior="overwrite_or_ignore",
        )

        total_rows = len(df)
        logger.info(
            "Bronze write complete: %s | %d rows | partitions=%s",
            out_path,
            total_rows,
            partition_cols,
        )
        return out_path

    def read(self, dataset_name: str = "orders", filters: Optional[list] = None) -> pd.DataFrame:
        """Read from Bronze Parquet layer with optional partition filter."""
        path = self.output_dir / dataset_name
        if not path.exists():
            raise FileNotFoundError(f"Bronze dataset not found: {path}")

        table = pq.read_table(str(path), filters=filters)
        df = table.to_pandas()
        logger.info("Read %d rows from Bronze: %s", len(df), path)
        return df

    @staticmethod
    def _add_metadata(df: pd.DataFrame) -> pd.DataFrame:
        """Stamp each row with pipeline lineage metadata."""
        now = datetime.utcnow().isoformat()
        df = df.copy()
        df["_ingested_at"] = now
        df["_layer"] = "bronze"
        return df
