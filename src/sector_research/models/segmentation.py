"""Unsupervised customer segmentation with K-Means on RFM features.

We log-transform and standardise the skewed RFM features, scan ``k`` using the
elbow (inertia) and silhouette score, fit the configured number of clusters and
attach a business-friendly persona to each segment.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ..config import Config, get_logger
from ..viz.theme import PALETTE, apply_theme, savefig

logger = get_logger(__name__)


def _prepare_matrix(feats: pd.DataFrame, features: list[str]) -> np.ndarray:
    """Log1p + standardise the (right-skewed) RFM features."""
    X = feats[features].to_numpy(dtype=float)
    X = np.log1p(np.clip(X, a_min=0, a_max=None))
    return StandardScaler().fit_transform(X)


def scan_k(feats: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Evaluate candidate ``k`` values by inertia and silhouette."""
    seg = cfg["segmentation"]
    X = _prepare_matrix(feats, seg["features"])
    rows = []
    for k in seg["k_scan"]:
        km = KMeans(n_clusters=k, random_state=cfg.random_state, n_init=10)
        labels = km.fit_predict(X)
        rows.append(
            {"k": k, "inertia": km.inertia_, "silhouette": silhouette_score(X, labels)}
        )
    return pd.DataFrame(rows)


def plot_k_scan(scan: pd.DataFrame, fig_dir: Path) -> None:
    apply_theme()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(scan["k"], scan["inertia"], marker="o", color=PALETTE[0])
    ax1.set_title("Elbow (inertia)")
    ax1.set_xlabel("k")
    ax2.plot(scan["k"], scan["silhouette"], marker="o", color=PALETTE[1])
    ax2.set_title("Silhouette score")
    ax2.set_xlabel("k")
    savefig(fig, fig_dir / "05_kmeans_scan.png", "Choosing the Number of Segments")


def fit_segments(feats: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, KMeans]:
    """Fit K-Means and attach cluster labels + personas to the feature table."""
    seg = cfg["segmentation"]
    X = _prepare_matrix(feats, seg["features"])
    km = KMeans(n_clusters=seg["n_clusters"], random_state=cfg.random_state, n_init=10)
    labels = km.fit_predict(X)

    out = feats.copy()
    out["cluster"] = labels
    out["persona"] = _assign_personas(out, seg["features"])
    return out, km


def _assign_personas(df: pd.DataFrame, features: list[str]) -> pd.Series:
    """Rank clusters by value and map them to ordered personas.

    Personas are derived from each cluster's monetary & frequency rank versus
    recency, so the labels stay meaningful regardless of cluster numbering.
    """
    profile = df.groupby("cluster").agg(
        recency=("recency", "median"),
        frequency=("frequency", "median"),
        monetary=("monetary", "median"),
    )
    # Composite value score: high frequency & monetary, low recency = best.
    score = (
        profile["monetary"].rank() + profile["frequency"].rank() - profile["recency"].rank()
    ).sort_values(ascending=False)

    persona_names = [
        "Champions",          # best overall
        "Loyal Customers",
        "Potential / Recent",
        "At-Risk / Dormant",  # worst overall
        "Low-Value Occasional",
        "Hibernating",
        "One-Time Buyers",
        "Lapsed",
    ]
    mapping = {cluster: persona_names[min(i, len(persona_names) - 1)]
               for i, cluster in enumerate(score.index)}
    return df["cluster"].map(mapping)


def segment_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Summarise each segment for the report."""
    prof = (
        df.groupby(["cluster", "persona"])
        .agg(
            customers=("customer_id", "count"),
            recency=("recency", "median"),
            frequency=("frequency", "median"),
            monetary=("monetary", "median"),
            total_revenue=("monetary", "sum"),
        )
        .reset_index()
        .sort_values("total_revenue", ascending=False)
    )
    prof["revenue_share"] = prof["total_revenue"] / prof["total_revenue"].sum()
    prof["customer_share"] = prof["customers"] / prof["customers"].sum()
    return prof


def plot_segments(df: pd.DataFrame, fig_dir: Path) -> None:
    """Scatter of frequency vs monetary coloured by segment, sized by recency."""
    apply_theme()
    fig, ax = plt.subplots()
    for i, (persona, grp) in enumerate(df.groupby("persona")):
        ax.scatter(
            grp["frequency"], grp["monetary"], s=18, alpha=0.5,
            color=PALETTE[i % len(PALETTE)], label=persona,
        )
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Frequency (orders, log)")
    ax.set_ylabel("Monetary (£, log)")
    ax.legend(markerscale=2, fontsize=9)
    savefig(fig, fig_dir / "06_customer_segments.png", "Customer Segments (Frequency × Monetary)")


def run_segmentation(feats: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Full segmentation step: scan k, fit, profile and plot."""
    fig_dir = cfg.path(cfg["paths"]["figures"])
    fig_dir.mkdir(parents=True, exist_ok=True)

    scan = scan_k(feats, cfg)
    plot_k_scan(scan, fig_dir)
    best_k = int(scan.loc[scan["silhouette"].idxmax(), "k"])
    logger.info("Silhouette-optimal k=%s (using configured k=%s)", best_k, cfg["segmentation"]["n_clusters"])

    segmented, _ = fit_segments(feats, cfg)
    profile = segment_profile(segmented)
    plot_segments(segmented, fig_dir)

    out = cfg.path(cfg["paths"]["reports"]) / "segment_profile.csv"
    profile.to_csv(out, index=False)
    logger.info("Segmentation complete — %s segments, profile saved to %s",
                cfg["segmentation"]["n_clusters"], out)
    return segmented, profile
