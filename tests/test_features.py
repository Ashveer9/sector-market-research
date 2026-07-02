"""Tests for RFM / customer feature engineering."""
from __future__ import annotations

import pandas as pd

from sector_research.features.rfm import build_customer_features, rfm_scores


def test_one_row_per_customer(clean_transactions_df, cfg):
    feats = build_customer_features(clean_transactions_df, cfg)
    assert feats["customer_id"].is_unique
    assert set(feats["customer_id"]) == set(clean_transactions_df["customer_id"])


def test_frequency_counts_distinct_invoices(clean_transactions_df, cfg):
    feats = build_customer_features(clean_transactions_df, cfg).set_index("customer_id")
    # Customer 13047 has invoices 536367 and 536380 => frequency 2.
    assert feats.loc[13047, "frequency"] == 2
    # Customer 17850 has invoices 536365 and 536366 => frequency 2.
    assert feats.loc[17850, "frequency"] == 2


def test_monetary_matches_revenue_sum(clean_transactions_df, cfg):
    feats = build_customer_features(clean_transactions_df, cfg).set_index("customer_id")
    expected = clean_transactions_df.groupby("customer_id")["revenue"].sum()
    for cust, val in expected.items():
        assert feats.loc[cust, "monetary"] == val


def test_recency_non_negative(clean_transactions_df, cfg):
    feats = build_customer_features(clean_transactions_df, cfg)
    assert (feats["recency"] >= 0).all()


def test_avg_order_value_consistent(clean_transactions_df, cfg):
    feats = build_customer_features(clean_transactions_df, cfg)
    pd.testing.assert_series_equal(
        feats["avg_order_value"],
        feats["monetary"] / feats["frequency"],
        check_names=False,
    )


def test_rfm_scores_in_range(clean_transactions_df, cfg):
    feats = rfm_scores(build_customer_features(clean_transactions_df, cfg))
    for col in ["r_score", "f_score", "m_score"]:
        assert feats[col].between(1, 5).all()
    assert feats["rfm_segment"].notna().all()
