"""Tests for segmentation and churn on a larger synthetic transaction log.

Two-customer fixtures cannot support clustering or a train/test split, so these
tests synthesise a few hundred customers with controllable behaviour.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from sector_research.features.rfm import build_customer_features
from sector_research.models.churn import build_churn_frame, train_churn
from sector_research.models.segmentation import fit_segments, scan_k


@pytest.fixture
def synthetic_log() -> pd.DataFrame:
    """~400 customers across a year with a mix of loyal and one-off buyers."""
    rng = np.random.default_rng(0)
    start = pd.Timestamp("2011-01-01")
    records = []
    for cust in range(400):
        n_orders = int(rng.integers(1, 15))
        base_price = rng.uniform(1.5, 8.0)
        for _ in range(n_orders):
            day = int(rng.integers(0, 330))
            invoice = f"{cust:04d}-{day:03d}"
            for _ in range(int(rng.integers(1, 4))):  # a few lines per invoice
                records.append(
                    {
                        "invoice": invoice,
                        "stock_code": f"SKU{int(rng.integers(0, 60)):03d}",
                        "description": "ITEM",
                        "quantity": int(rng.integers(1, 20)),
                        "invoice_date": start + pd.Timedelta(days=day),
                        "price": round(base_price, 2),
                        "customer_id": 10000 + cust,
                        "country": "United Kingdom",
                    }
                )
    df = pd.DataFrame.from_records(records)
    df["revenue"] = df["quantity"] * df["price"]
    df["order_date"] = df["invoice_date"].dt.normalize()
    df["year_month"] = df["invoice_date"].dt.to_period("M").astype(str)
    return df


def test_scan_k_returns_metrics(synthetic_log, cfg):
    feats = build_customer_features(synthetic_log, cfg)
    scan = scan_k(feats, cfg)
    assert set(scan.columns) == {"k", "inertia", "silhouette"}
    assert (scan["silhouette"].between(-1, 1)).all()
    # Inertia should be monotonically non-increasing in k.
    assert (scan.sort_values("k")["inertia"].diff().dropna() <= 1e-6).all()


def test_fit_segments_labels_every_customer(synthetic_log, cfg):
    feats = build_customer_features(synthetic_log, cfg)
    segmented, km = fit_segments(feats, cfg)
    assert segmented["cluster"].notna().all()
    assert segmented["persona"].notna().all()
    assert km.n_clusters == cfg["segmentation"]["n_clusters"]
    assert segmented["cluster"].nunique() == cfg["segmentation"]["n_clusters"]


def test_churn_frame_is_binary_and_leakage_safe(synthetic_log, cfg):
    feats, cutoff = build_churn_frame(synthetic_log, cfg)
    assert set(feats["churned"].unique()) <= {0, 1}
    # Every feature customer must have transacted on or before the cutoff.
    assert feats["last_purchase"].max() <= cutoff


def test_train_churn_produces_valid_metrics(synthetic_log, cfg, tmp_path, monkeypatch):
    # Redirect model/figure output into a temp dir so tests stay hermetic.
    monkeypatch.setitem(cfg._data["paths"], "models", str(tmp_path / "models"))
    monkeypatch.setitem(cfg._data["paths"], "figures", str(tmp_path / "figs"))
    metrics = train_churn(synthetic_log, cfg)
    assert 0.0 <= metrics["roc_auc"] <= 1.0
    assert 0.0 <= metrics["pr_auc"] <= 1.0
    assert metrics["best_model"] in {"logistic_regression", "gradient_boosting"}
    assert (tmp_path / "models" / "churn_model.joblib").exists()
