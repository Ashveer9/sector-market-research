"""Tests for the cleaning business rules."""
from __future__ import annotations

import pandas as pd

from sector_research.data.clean import clean_transactions


def test_removes_all_invalid_rows(clean_transactions_df):
    df = clean_transactions_df
    # From 11 raw rows only 5 valid purchases remain (see conftest for the cases).
    assert len(df) == 5


def test_no_cancellations_survive(clean_transactions_df):
    assert not clean_transactions_df["invoice"].str.startswith("C").any()


def test_no_missing_customers(clean_transactions_df):
    assert clean_transactions_df["customer_id"].notna().all()
    assert clean_transactions_df["customer_id"].dtype.kind in "iu"


def test_positive_quantity_and_price(clean_transactions_df):
    assert (clean_transactions_df["quantity"] > 0).all()
    assert (clean_transactions_df["price"] > 0).all()


def test_service_codes_removed(clean_transactions_df):
    assert "POST" not in set(clean_transactions_df["stock_code"])


def test_revenue_column_is_correct(clean_transactions_df):
    df = clean_transactions_df
    expected = df["quantity"] * df["price"]
    pd.testing.assert_series_equal(df["revenue"], expected, check_names=False)


def test_derived_calendar_columns(clean_transactions_df):
    df = clean_transactions_df
    assert "year_month" in df.columns
    assert df["order_date"].equals(df["invoice_date"].dt.normalize())


def test_idempotent_on_clean_input(clean_transactions_df, cfg):
    """Cleaning already-clean data (re-renamed) should be a no-op on row count."""
    twice = clean_transactions(clean_transactions_df, cfg)
    assert len(twice) == len(clean_transactions_df)
