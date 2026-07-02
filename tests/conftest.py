"""Shared fixtures: a small synthetic transaction log and a config.

The tests never touch the 45 MB real workbook — they run against a compact,
hand-built frame that exercises every cleaning rule and downstream aggregation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sector_research.config import load_config


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture
def raw_transactions() -> pd.DataFrame:
    """A tiny raw (renamed) frame containing one of every messy case."""
    rows = [
        # invoice, stock_code, description, quantity, invoice_date, price, customer_id, country
        ("536365", "85123A", "WHITE HANGING HEART", 6, "2011-01-01 08:00", 2.55, 17850, "United Kingdom"),
        ("536365", "71053", "WHITE METAL LANTERN", 6, "2011-01-01 08:00", 3.39, 17850, "United Kingdom"),
        ("536366", "84406B", "CREAM CUPID HEARTS", 8, "2011-02-01 09:00", 2.75, 17850, "United Kingdom"),
        ("536367", "22745", "POPPY'S PLAYHOUSE", 6, "2011-03-01 10:00", 3.75, 13047, "France"),
        # cancellation (dropped)
        ("C536368", "22745", "POPPY'S PLAYHOUSE", -6, "2011-03-02 10:00", 3.75, 13047, "France"),
        # service code (dropped)
        ("536369", "POST", "POSTAGE", 1, "2011-03-03 10:00", 18.0, 13047, "France"),
        # missing customer (dropped)
        ("536370", "85123A", "WHITE HANGING HEART", 3, "2011-03-04 10:00", 2.55, np.nan, "United Kingdom"),
        # non-positive price (dropped)
        ("536371", "84406B", "CREAM CUPID HEARTS", 4, "2011-03-05 10:00", 0.0, 13047, "France"),
        # non-positive quantity (dropped)
        ("536372", "84406B", "CREAM CUPID HEARTS", -2, "2011-03-06 10:00", 2.75, 13047, "France"),
        # exact duplicate of the first row (dropped)
        ("536365", "85123A", "WHITE HANGING HEART", 6, "2011-01-01 08:00", 2.55, 17850, "United Kingdom"),
        # repeat buyer, later month
        ("536380", "22745", "POPPY'S PLAYHOUSE", 10, "2011-06-01 11:00", 3.75, 13047, "France"),
    ]
    cols = ["invoice", "stock_code", "description", "quantity",
            "invoice_date", "price", "customer_id", "country"]
    df = pd.DataFrame(rows, columns=cols)
    df["invoice_date"] = pd.to_datetime(df["invoice_date"])
    return df


@pytest.fixture
def clean_transactions_df(raw_transactions, cfg):
    from sector_research.data.clean import clean_transactions
    return clean_transactions(raw_transactions, cfg)
