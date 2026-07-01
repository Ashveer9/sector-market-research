"""
Silver layer transformer: cleanses and type-casts Bronze data.
Applies: null handling, deduplication, type coercion, derived columns.
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

DATE_FORMATS = ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%m-%Y"]


class SilverTransformer:
    """Transforms Bronze raw data into a cleansed Silver Parquet dataset."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or config.processed_path
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all cleansing steps and return a Silver-grade DataFrame."""
        logger.info("Starting Silver transformation on %d rows", len(df))
        original_count = len(df)

        df = self._drop_pipeline_metadata(df)
        df = self._parse_dates(df)
        df = self._cast_numerics(df)
        df = self._clean_strings(df)
        df = self._handle_nulls(df)
        df = self._deduplicate(df)
        df = self._add_derived_columns(df)
        df = self._add_metadata(df)

        logger.info(
            "Silver transformation complete: %d → %d rows (dropped %d)",
            original_count,
            len(df),
            original_count - len(df),
        )
        return df

    def write(self, df: pd.DataFrame, dataset_name: str = "orders") -> Path:
        """Write transformed DataFrame to Silver Parquet store."""
        out_path = self.output_dir / dataset_name
        out_path.mkdir(parents=True, exist_ok=True)

        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_to_dataset(
            table,
            root_path=str(out_path),
            partition_cols=["market"] if "market" in df.columns else None,
            compression=config.get("pipeline", "silver_compression", default="zstd"),
            existing_data_behavior="overwrite_or_ignore",
        )
        logger.info("Silver data written to %s", out_path)
        return out_path

    def read(self, dataset_name: str = "orders") -> pd.DataFrame:
        """Read Silver Parquet dataset."""
        path = self.output_dir / dataset_name
        if not path.exists():
            raise FileNotFoundError(f"Silver dataset not found: {path}")
        table = pq.read_table(str(path))
        df = table.to_pandas()
        logger.info("Read %d rows from Silver: %s", len(df), path)
        return df

    # ── Private cleansing steps ──────────────────────────────────────────

    @staticmethod
    def _drop_pipeline_metadata(df: pd.DataFrame) -> pd.DataFrame:
        meta_cols = [c for c in df.columns if c.startswith("_")]
        return df.drop(columns=meta_cols, errors="ignore")

    @staticmethod
    def _parse_dates(df: pd.DataFrame) -> pd.DataFrame:
        for col in ["order_date", "ship_date"]:
            if col not in df.columns:
                continue
            # Try multiple date formats
            parsed = None
            for fmt in DATE_FORMATS:
                try:
                    parsed = pd.to_datetime(df[col], format=fmt, errors="coerce")
                    if parsed.notna().mean() > 0.9:
                        break
                except Exception:
                    continue
            if parsed is None:
                parsed = pd.to_datetime(df[col], infer_datetime_format=True, errors="coerce")
            df[col] = parsed.dt.date
        return df

    @staticmethod
    def _cast_numerics(df: pd.DataFrame) -> pd.DataFrame:
        numeric_cols = {
            "sales": float,
            "quantity": int,
            "discount": float,
            "profit": float,
            "shipping_cost": float,
            "row_id": int,
        }
        for col, dtype in numeric_cols.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
                if dtype == int:
                    df[col] = df[col].fillna(0).astype("Int64")
        return df

    @staticmethod
    def _clean_strings(df: pd.DataFrame) -> pd.DataFrame:
        str_cols = [
            "order_id", "customer_id", "customer_name", "segment",
            "city", "state", "country", "market", "region",
            "product_id", "category", "sub_category", "product_name",
            "ship_mode", "order_priority",
        ]
        for col in str_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
                # Replace placeholder 'nan' strings with proper NaN
                df[col] = df[col].replace({"nan": pd.NA, "None": pd.NA, "": pd.NA})
        return df

    @staticmethod
    def _handle_nulls(df: pd.DataFrame) -> pd.DataFrame:
        # Drop rows missing critical business keys
        critical = ["order_id", "order_date", "customer_id", "product_id", "sales"]
        existing_critical = [c for c in critical if c in df.columns]
        before = len(df)
        df = df.dropna(subset=existing_critical)
        dropped = before - len(df)
        if dropped:
            logger.warning("Dropped %d rows with null critical columns", dropped)

        # Fill optional nulls
        fill_map = {
            "postal_code": "UNKNOWN",
            "shipping_cost": 0.0,
            "discount": 0.0,
        }
        df = df.copy()
        for col, fill in fill_map.items():
            if col in df.columns:
                df[col] = df[col].fillna(fill)

        return df

    @staticmethod
    def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
        key_cols = [c for c in ["order_id", "product_id"] if c in df.columns]
        if not key_cols:
            return df
        before = len(df)
        df = df.drop_duplicates(subset=key_cols, keep="first")
        dupes = before - len(df)
        if dupes:
            logger.info("Removed %d duplicate rows", dupes)
        return df

    @staticmethod
    def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Compute business-useful derived fields."""
        if "profit" in df.columns and "sales" in df.columns:
            df["profit_margin"] = (
                df["profit"] / df["sales"].replace(0, pd.NA)
            ).round(4)

        if "order_date" in df.columns:
            dates = pd.to_datetime(df["order_date"])
            df["order_year"] = dates.dt.year
            df["order_quarter"] = dates.dt.quarter
            df["order_month"] = dates.dt.month
            df["order_week"] = dates.dt.isocalendar().week.astype("Int32")

        if "order_date" in df.columns and "ship_date" in df.columns:
            ship = pd.to_datetime(df["ship_date"], errors="coerce")
            order = pd.to_datetime(df["order_date"], errors="coerce")
            df["days_to_ship"] = (ship - order).dt.days.astype("Int32")

        return df

    @staticmethod
    def _add_metadata(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["_processed_at"] = datetime.utcnow().isoformat()
        df["_layer"] = "silver"
        return df
