"""Customer feature engineering: RFM and behavioural attributes.

RFM (Recency, Frequency, Monetary) is the workhorse of retail customer
analytics. We extend the classic triple with behavioural features (tenure,
average order value, basket size, product breadth, return rate) so the same
table can feed both segmentation and the churn model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import Config, get_logger, load_config

logger = get_logger(__name__)


def _snapshot_date(df: pd.DataFrame) -> pd.Timestamp:
    """Reference 'today' for recency: one day after the last transaction."""
    return df["invoice_date"].max() + pd.Timedelta(days=1)


def build_customer_features(
    df: pd.DataFrame,
    cfg: Config,
    snapshot: pd.Timestamp | None = None,
    returns: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Aggregate the transaction log to one row per customer.

    Parameters
    ----------
    df:
        Cleaned transactions (positive-quantity purchases only).
    returns:
        Optional frame of return line items (negative quantity, pre-filtered)
        used to compute ``return_rate``. When ``None`` the rate is 0.
    snapshot:
        Recency reference date. Defaults to one day after the last purchase.
    """
    snapshot = snapshot or _snapshot_date(df)

    grp = df.groupby("customer_id")
    feats = pd.DataFrame(
        {
            "recency": (snapshot - grp["invoice_date"].max()).dt.days,
            "frequency": grp["invoice"].nunique(),
            "monetary": grp["revenue"].sum(),
            "first_purchase": grp["invoice_date"].min(),
            "last_purchase": grp["invoice_date"].max(),
            "distinct_products": grp["stock_code"].nunique(),
            "total_units": grp["quantity"].sum(),
        }
    )
    feats["tenure_days"] = (snapshot - feats["first_purchase"]).dt.days
    feats["avg_order_value"] = feats["monetary"] / feats["frequency"]
    feats["avg_basket_size"] = feats["total_units"] / feats["frequency"]

    # Return rate: returned units / purchased units (0 when no returns supplied).
    if returns is not None and len(returns):
        ret_units = returns.groupby("customer_id")["quantity"].apply(lambda s: s.abs().sum())
        feats["returned_units"] = ret_units.reindex(feats.index).fillna(0)
    else:
        feats["returned_units"] = 0.0
    feats["return_rate"] = feats["returned_units"] / (feats["total_units"] + feats["returned_units"])
    feats["return_rate"] = feats["return_rate"].fillna(0.0)

    feats = feats.reset_index()
    logger.info("Built features for %s customers", f"{len(feats):,}")
    return feats


def rfm_scores(feats: pd.DataFrame) -> pd.DataFrame:
    """Add quintile R/F/M scores (1–5) and an 'RFM segment' label.

    Recency is reverse-scored (more recent = higher). Frequency and monetary
    are forward-scored. Scores feed an interpretable rule-based segment that
    complements the unsupervised clusters.
    """
    out = feats.copy()
    out["r_score"] = _quintile(out["recency"], reverse=True)
    out["f_score"] = _quintile(out["frequency"].rank(method="first"), reverse=False)
    out["m_score"] = _quintile(out["monetary"], reverse=False)
    out["rfm_sum"] = out[["r_score", "f_score", "m_score"]].sum(axis=1)
    out["rfm_segment"] = out.apply(_label_segment, axis=1)
    return out


def _quintile(series: pd.Series, reverse: bool) -> pd.Series:
    """Robust 1–5 quintile scoring that tolerates ties / sparse values."""
    try:
        q = pd.qcut(series, 5, labels=False, duplicates="drop")
    except ValueError:
        q = pd.Series(np.zeros(len(series)), index=series.index)
    # Normalise to a 1..5 range regardless of how many bins survived.
    q = q.astype(float)
    span = q.max() - q.min()
    if span == 0:
        scaled = pd.Series(np.full(len(series), 3), index=series.index)
    else:
        scaled = 1 + 4 * (q - q.min()) / span
    scaled = scaled.round().astype(int)
    return (6 - scaled) if reverse else scaled


def _label_segment(row: pd.Series) -> str:
    """Map R/F/M scores to a human-readable marketing segment."""
    r, f, m = row["r_score"], row["f_score"], row["m_score"]
    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"
    if r >= 3 and f >= 3:
        return "Loyal"
    if r >= 4 and f <= 2:
        return "New / Promising"
    if r <= 2 and f >= 3 and m >= 3:
        return "At Risk"
    if r <= 2 and f <= 2:
        return "Hibernating"
    return "Needs Attention"


def build_and_save_features(cfg: Config | None = None, df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build customer features from the cleaned data and persist them."""
    from ..data.clean import load_clean

    cfg = cfg or load_config()
    if df is None:
        df = load_clean(cfg)
    feats = rfm_scores(build_customer_features(df, cfg))

    out = cfg.path(cfg["data"]["customers_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(out, index=False)
    logger.info("Wrote customer features to %s", out)
    return feats
