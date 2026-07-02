"""Clean and validate the raw transaction log.

The raw workbook is a real-world operational export and contains the usual
messiness: cancellations, returns, service/admin line items, missing customer
IDs, zero-priced rows and duplicates. This module encodes the business rules
that turn it into an analysis-ready table, and exposes them as small, testable
functions.
"""
from __future__ import annotations

import pandas as pd

from ..config import Config, get_logger, load_config

logger = get_logger(__name__)

# Canonical column names used throughout the package.
COLUMNS = {
    "Invoice": "invoice",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "Price": "price",
    "Customer ID": "customer_id",
    "Country": "country",
}


def load_raw(cfg: Config) -> pd.DataFrame:
    """Read and concatenate both yearly sheets of the raw workbook."""
    raw_path = cfg.path(cfg["data"]["raw_path"])
    logger.info("Reading raw workbook %s", raw_path)
    sheets = pd.read_excel(raw_path, sheet_name=None)  # dict of all sheets
    frames = []
    for name, frame in sheets.items():
        logger.info("  sheet '%s': %s rows", name, f"{len(frame):,}")
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    return df.rename(columns=COLUMNS)


def clean_transactions(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Apply business-rule cleaning to a raw (renamed) transaction frame.

    Steps, in order:
      1. Normalise dtypes and strip whitespace.
      2. Flag cancellations (invoices prefixed with "C") and drop them.
      3. Remove non-product service/admin stock codes.
      4. Drop rows with missing customer IDs (cannot be attributed).
      5. Drop non-positive quantity / price rows.
      6. Drop exact duplicates.
      7. Derive ``revenue = quantity * price`` and calendar helper columns.
    """
    rules = cfg["cleaning"]
    n0 = len(df)
    df = df.copy()

    # 1. dtype + whitespace normalisation
    df["invoice"] = df["invoice"].astype(str).str.strip()
    df["stock_code"] = df["stock_code"].astype(str).str.strip().str.upper()
    df["description"] = df["description"].astype("string").str.strip()
    df["country"] = df["country"].astype("string").str.strip()
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])

    # 2. cancellations
    is_cancellation = df["invoice"].str.startswith(rules["cancellation_prefix"], na=False)
    n_cancel = int(is_cancellation.sum())
    df = df.loc[~is_cancellation]

    # 3. service / admin line items
    service = {c.upper() for c in rules["service_stock_codes"]}
    is_service = df["stock_code"].isin(service)
    n_service = int(is_service.sum())
    df = df.loc[~is_service]

    # 4. missing customer ids
    n_missing = 0
    if rules["drop_missing_customer"]:
        missing = df["customer_id"].isna()
        n_missing = int(missing.sum())
        df = df.loc[~missing]
    df["customer_id"] = df["customer_id"].astype("int64")

    # 5. non-positive quantity / price
    valid = (df["quantity"] >= rules["min_quantity"]) & (df["price"] >= rules["min_price"])
    n_invalid = int((~valid).sum())
    df = df.loc[valid]

    # 6. exact duplicates
    n_dupes = int(df.duplicated().sum())
    df = df.drop_duplicates()

    # 7. derived columns
    df["revenue"] = df["quantity"] * df["price"]
    df["invoice_date"] = df["invoice_date"].dt.tz_localize(None)
    df["order_date"] = df["invoice_date"].dt.normalize()
    df["year_month"] = df["invoice_date"].dt.to_period("M").astype(str)

    df = df.reset_index(drop=True)
    logger.info(
        "Cleaning summary: %s -> %s rows kept "
        "(cancellations=%s, service=%s, missing_id=%s, invalid_qty_price=%s, dupes=%s)",
        f"{n0:,}", f"{len(df):,}", f"{n_cancel:,}", f"{n_service:,}",
        f"{n_missing:,}", f"{n_invalid:,}", f"{n_dupes:,}",
    )
    return df


def build_clean_dataset(cfg: Config | None = None) -> pd.DataFrame:
    """Full data-prep step: load raw, clean, and persist to parquet."""
    cfg = cfg or load_config()
    raw = load_raw(cfg)
    clean = clean_transactions(raw, cfg)

    out_path = cfg.path(cfg["data"]["processed_path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    clean.to_parquet(out_path, index=False)
    logger.info("Wrote cleaned dataset to %s", out_path)
    return clean


def load_clean(cfg: Config) -> pd.DataFrame:
    """Load the persisted cleaned dataset, building it if necessary."""
    path = cfg.path(cfg["data"]["processed_path"])
    if not path.exists():
        return build_clean_dataset(cfg)
    return pd.read_parquet(path)


if __name__ == "__main__":
    build_clean_dataset()
