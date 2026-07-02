"""Cohort retention analysis.

Customers are grouped into monthly acquisition cohorts (the month of their
first purchase). For each cohort we measure the share still active in each
subsequent month — the canonical retention triangle.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from ..config import Config, get_logger
from ..viz.theme import apply_theme, savefig

logger = get_logger(__name__)


def build_cohorts(df: pd.DataFrame) -> pd.DataFrame:
    """Return a retention matrix: rows = acquisition cohort, cols = month offset."""
    data = df[["customer_id", "invoice_date"]].copy()
    data["order_month"] = data["invoice_date"].dt.to_period("M")
    data["cohort"] = data.groupby("customer_id")["order_month"].transform("min")

    # Integer month offset from the cohort's acquisition month.
    data["offset"] = (
        (data["order_month"].dt.year - data["cohort"].dt.year) * 12
        + (data["order_month"].dt.month - data["cohort"].dt.month)
    )

    counts = (
        data.groupby(["cohort", "offset"])["customer_id"].nunique().reset_index()
    )
    matrix = counts.pivot(index="cohort", columns="offset", values="customer_id")
    cohort_sizes = matrix.iloc[:, 0]
    retention = matrix.divide(cohort_sizes, axis=0)
    retention.index = retention.index.astype(str)
    return retention


def plot_cohorts(retention: pd.DataFrame, fig_dir: Path) -> None:
    """Render the retention triangle as an annotated heatmap."""
    apply_theme()
    fig, ax = plt.subplots(figsize=(12, 8))
    data = retention.to_numpy(dtype=float)
    im = ax.imshow(data, aspect="auto", cmap="YlGnBu", vmin=0, vmax=min(1.0, np.nanmax(data)))

    ax.set_xticks(range(retention.shape[1]))
    ax.set_xticklabels(retention.columns)
    ax.set_yticks(range(retention.shape[0]))
    ax.set_yticklabels(retention.index, fontsize=8)
    ax.set_xlabel("Months since first purchase")
    ax.set_ylabel("Acquisition cohort")
    ax.grid(False)

    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            v = data[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0%}", ha="center", va="center",
                        fontsize=6.5, color="black" if v < 0.5 else "white")
    fig.colorbar(im, ax=ax, label="Retention", fraction=0.025)
    savefig(fig, fig_dir / "04_cohort_retention.png", "Monthly Cohort Retention")


def run_cohort(df: pd.DataFrame, cfg: Config) -> dict:
    """Build cohorts, plot the heatmap and return summary retention metrics."""
    fig_dir = cfg.path(cfg["paths"]["figures"])
    fig_dir.mkdir(parents=True, exist_ok=True)
    retention = build_cohorts(df)
    plot_cohorts(retention, fig_dir)

    # Average retention at fixed offsets across cohorts (ignoring the 100% origin).
    def avg_at(offset: int) -> float:
        if offset in retention.columns:
            return float(retention[offset].mean(skipna=True))
        return float("nan")

    metrics = {
        "month_1_retention": avg_at(1),
        "month_3_retention": avg_at(3),
        "month_6_retention": avg_at(6),
        "n_cohorts": int(retention.shape[0]),
    }
    logger.info("Cohort analysis — avg month-1 retention %.1f%%", 100 * metrics["month_1_retention"])
    return metrics
