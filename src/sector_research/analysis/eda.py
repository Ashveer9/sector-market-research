"""Exploratory market analysis: revenue trends, geography and product mix.

Each function returns a tidy summary table *and* writes a figure, so the same
code powers both the report figures and the metrics surfaced in the README /
executive summary.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from ..config import Config, get_logger
from ..viz.theme import PALETTE, PRIMARY, apply_theme, savefig

logger = get_logger(__name__)


def market_overview(df: pd.DataFrame) -> dict:
    """Headline KPIs for the whole observation window."""
    kpis = {
        "rows": int(len(df)),
        "orders": int(df["invoice"].nunique()),
        "customers": int(df["customer_id"].nunique()),
        "products": int(df["stock_code"].nunique()),
        "countries": int(df["country"].nunique()),
        "total_revenue": float(df["revenue"].sum()),
        "avg_order_value": float(df.groupby("invoice")["revenue"].sum().mean()),
        "date_min": str(df["invoice_date"].min().date()),
        "date_max": str(df["invoice_date"].max().date()),
    }
    return kpis


def monthly_revenue(df: pd.DataFrame, fig_dir: Path) -> pd.DataFrame:
    """Monthly revenue and active-customer trend."""
    apply_theme()
    monthly = (
        df.groupby("year_month")
        .agg(revenue=("revenue", "sum"), customers=("customer_id", "nunique"),
             orders=("invoice", "nunique"))
        .reset_index()
    )
    monthly["month"] = pd.PeriodIndex(monthly["year_month"], freq="M").to_timestamp()

    fig, ax1 = plt.subplots()
    ax1.bar(monthly["month"], monthly["revenue"], width=20, color=PRIMARY, alpha=0.85, label="Revenue")
    ax1.set_ylabel("Revenue (£)")
    ax1.set_xlabel("Month")
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"£{v/1e3:,.0f}k"))

    ax2 = ax1.twinx()
    ax2.plot(monthly["month"], monthly["customers"], color=PALETTE[2], marker="o", lw=2, label="Active customers")
    ax2.set_ylabel("Active customers")
    ax2.grid(False)
    fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.95))
    savefig(fig, fig_dir / "01_monthly_revenue.png", "Monthly Revenue & Active Customers")
    return monthly


def revenue_by_country(df: pd.DataFrame, fig_dir: Path, top_n: int = 10) -> pd.DataFrame:
    """Revenue concentration by country (the geographic market view)."""
    apply_theme()
    by_country = (
        df.groupby("country")["revenue"].sum().sort_values(ascending=False).reset_index()
    )
    by_country["share"] = by_country["revenue"] / by_country["revenue"].sum()
    top = by_country.head(top_n).iloc[::-1]

    fig, ax = plt.subplots()
    ax.barh(top["country"], top["revenue"], color=PRIMARY)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"£{v/1e3:,.0f}k"))
    ax.set_xlabel("Revenue")
    for y, (rev, share) in enumerate(zip(top["revenue"], top["share"], strict=False)):
        ax.text(rev, y, f"  {share:.0%}", va="center", fontsize=9)
    savefig(fig, fig_dir / "02_revenue_by_country.png", f"Top {top_n} Markets by Revenue")
    return by_country


def top_products(df: pd.DataFrame, fig_dir: Path, top_n: int = 15) -> pd.DataFrame:
    """Best-selling products by revenue."""
    apply_theme()
    prod = (
        df.groupby(["stock_code", "description"])
        .agg(revenue=("revenue", "sum"), units=("quantity", "sum"))
        .sort_values("revenue", ascending=False)
        .reset_index()
    )
    top = prod.head(top_n).iloc[::-1]
    labels = top["description"].fillna(top["stock_code"]).str.title().str.slice(0, 32)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(labels, top["revenue"], color=PALETTE[1])
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"£{v/1e3:,.0f}k"))
    ax.set_xlabel("Revenue")
    savefig(fig, fig_dir / "03_top_products.png", f"Top {top_n} Products by Revenue")
    return prod


def revenue_pareto(df: pd.DataFrame) -> dict:
    """Quantify revenue concentration (the 80/20 story)."""
    cust_rev = df.groupby("customer_id")["revenue"].sum().sort_values(ascending=False)
    cum_share = cust_rev.cumsum() / cust_rev.sum()
    top20_cut = int(len(cust_rev) * 0.2)
    return {
        "revenue_from_top_20pct_customers": float(cum_share.iloc[top20_cut - 1]) if top20_cut else 0.0,
        "customers_for_80pct_revenue_share": float((cum_share <= 0.8).sum() / len(cust_rev)),
    }


def run_eda(df: pd.DataFrame, cfg: Config) -> dict:
    """Run the full EDA suite and return a metrics dictionary."""
    fig_dir = cfg.path(cfg["paths"]["figures"])
    fig_dir.mkdir(parents=True, exist_ok=True)

    kpis = market_overview(df)
    monthly_revenue(df, fig_dir)
    by_country = revenue_by_country(df, fig_dir)
    top_products(df, fig_dir)
    pareto = revenue_pareto(df)

    kpis["uk_revenue_share"] = float(
        by_country.set_index("country")["share"].get("United Kingdom", 0.0)
    )
    kpis.update(pareto)
    logger.info("EDA complete — total revenue £%.0f across %s orders", kpis["total_revenue"], f"{kpis['orders']:,}")
    return kpis
