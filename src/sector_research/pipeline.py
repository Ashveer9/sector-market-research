"""Pipeline orchestrator and CLI.

Run the whole project, or an individual stage, from one entry point:

    python -m sector_research.pipeline all          # everything
    python -m sector_research.pipeline clean         # just data prep
    python -m sector_research.pipeline segment       # segmentation only

Stage outputs (figures, CSVs, model, metrics JSON, executive summary) land in
``reports/`` and ``models/``.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from .analysis.cohort import run_cohort
from .analysis.eda import run_eda
from .analysis.market_basket import run_market_basket
from .config import Config, get_logger, load_config
from .data.clean import build_clean_dataset, load_clean
from .data.download import download_raw
from .features.rfm import build_and_save_features
from .models.churn import run_churn
from .models.segmentation import run_segmentation

logger = get_logger("sector_research.pipeline")


def _write_metrics(cfg: Config, metrics: dict) -> None:
    out = cfg.path(cfg["paths"]["reports"]) / "metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2, default=str)
    logger.info("Wrote consolidated metrics to %s", out)


def run_all(cfg: Config) -> dict:
    """Execute the full pipeline and return a consolidated metrics dictionary."""
    metrics: dict = {"generated_at": datetime.now(timezone.utc).isoformat()}

    download_raw(cfg)
    df = build_clean_dataset(cfg)
    feats = build_and_save_features(cfg, df=df)

    metrics["eda"] = run_eda(df, cfg)
    metrics["cohort"] = run_cohort(df, cfg)

    _segmented, profile = run_segmentation(feats, cfg)
    metrics["segmentation"] = {
        "n_segments": int(cfg["segmentation"]["n_clusters"]),
        "segments": profile[["persona", "customers", "revenue_share", "monetary"]].to_dict("records"),
    }

    rules = run_market_basket(df, cfg)
    metrics["market_basket"] = {
        "n_rules": int(len(rules)),
        "top_rules": rules.head(5).to_dict("records") if not rules.empty else [],
    }

    metrics["churn"] = run_churn(df, cfg)

    _write_metrics(cfg, metrics)
    write_executive_summary(cfg, metrics)
    return metrics


def write_executive_summary(cfg: Config, metrics: dict) -> None:
    """Render a stakeholder-facing markdown summary from the metrics."""
    eda = metrics.get("eda", {})
    coh = metrics.get("cohort", {})
    churn = metrics.get("churn", {})
    seg = metrics.get("segmentation", {})
    basket = metrics.get("market_basket", {})

    def money(x):
        return f"£{x:,.0f}" if isinstance(x, (int, float)) else "n/a"

    def pct(x):
        return f"{100 * x:.1f}%" if isinstance(x, (int, float)) else "n/a"

    seg_lines = "\n".join(
        f"| {s['persona']} | {s['customers']:,} | {pct(s['revenue_share'])} | {money(s['monetary'])} |"
        for s in seg.get("segments", [])
    )

    rule_lines = "\n".join(
        f"| {r['antecedents_str']} | {r['consequents_str']} | {r['lift']:.1f} | {pct(r['confidence'])} |"
        for r in basket.get("top_rules", [])
    ) or "| _no rules above threshold_ | | | |"

    summary = f"""# Executive Summary — Retail Sector Market Research

_Generated {metrics.get('generated_at', '')[:10]} from {eda.get('date_min', '?')} → {eda.get('date_max', '?')} transactions._

## The market at a glance

| KPI | Value |
|---|---|
| Total revenue | {money(eda.get('total_revenue'))} |
| Orders | {eda.get('orders', 0):,} |
| Active customers | {eda.get('customers', 0):,} |
| Products sold | {eda.get('products', 0):,} |
| Markets (countries) | {eda.get('countries', 0)} |
| Average order value | {money(eda.get('avg_order_value'))} |
| UK revenue share | {pct(eda.get('uk_revenue_share'))} |
| Revenue from top 20% of customers | {pct(eda.get('revenue_from_top_20pct_customers'))} |

## Customer segments (K-Means on RFM)

| Segment | Customers | Revenue share | Median spend |
|---|---|---|---|
{seg_lines}

## Retention

- Average **month-1 retention**: **{pct(coh.get('month_1_retention'))}**
- Average **month-3 retention**: **{pct(coh.get('month_3_retention'))}**
- Average **month-6 retention**: **{pct(coh.get('month_6_retention'))}**

Retention drops sharply after the first month — a classic acquisition-heavy,
loyalty-light profile. Converting one-time buyers into a second purchase is the
single highest-leverage growth lever.

## Cross-sell opportunities (market-basket analysis)

Top product associations by lift ({basket.get('n_rules', 0)} rules mined):

| If basket contains | …customer also buys | Lift | Confidence |
|---|---|---|---|
{rule_lines}

## Churn prediction

A **{churn.get('best_model', 'model')}** trained on pre-cutoff behaviour predicts
which customers will lapse in the following {cfg['churn']['inactivity_days']} days:

- ROC-AUC: **{churn.get('roc_auc', float('nan')):.3f}**, PR-AUC: **{churn.get('pr_auc', float('nan')):.3f}**
- Recall on churners: **{pct(churn.get('recall_churn'))}**, precision: **{pct(churn.get('precision_churn'))}**
- Strongest churn signal: **{churn.get('top_feature', 'n/a')}**
- Baseline churn rate in the window: **{pct(churn.get('churn_rate'))}**

## Recommendations

1. **Protect the top 20%.** A small share of customers drives the majority of
   revenue — fund a retention / VIP programme for *Champions* and *Loyal*
   segments before chasing new acquisition.
2. **Win the second order.** With steep month-1 churn, a triggered post-first-
   purchase journey (day 14/30 incentives) targets the biggest leak.
3. **Operationalise the churn model.** Score customers monthly; route high-risk,
   high-value accounts to proactive outreach. Recall of {pct(churn.get('recall_churn'))}
   means most future churners are catchable.
4. **Bundle on the rules above.** Use the highest-lift associations for
   cross-sell on product pages, in baskets and in email.
5. **Diversify beyond the UK.** {pct(eda.get('uk_revenue_share'))} of revenue is
   single-market — the strongest EU markets are candidates for focused expansion.

---
*Figures referenced in this summary are in `reports/figures/`; full metrics in
`reports/metrics.json`.*
"""
    out = cfg.path(cfg["paths"]["reports"]) / "executive_summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(summary)
    logger.info("Wrote executive summary to %s", out)


# --- individual stage entry points -------------------------------------------

def _stage_clean(cfg: Config) -> None:
    download_raw(cfg)
    build_clean_dataset(cfg)


def _stage_features(cfg: Config) -> None:
    build_and_save_features(cfg)


def _stage_eda(cfg: Config) -> None:
    run_eda(load_clean(cfg), cfg)


def _stage_cohort(cfg: Config) -> None:
    run_cohort(load_clean(cfg), cfg)


def _stage_segment(cfg: Config) -> None:
    run_segmentation(build_and_save_features(cfg), cfg)


def _stage_basket(cfg: Config) -> None:
    run_market_basket(load_clean(cfg), cfg)


def _stage_churn(cfg: Config) -> None:
    run_churn(load_clean(cfg), cfg)


STAGES = {
    "clean": _stage_clean,
    "features": _stage_features,
    "eda": _stage_eda,
    "cohort": _stage_cohort,
    "segment": _stage_segment,
    "basket": _stage_basket,
    "churn": _stage_churn,
    "all": run_all,
}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Retail sector market-research pipeline")
    parser.add_argument("stage", choices=sorted(STAGES), nargs="?", default="all",
                        help="Pipeline stage to run (default: all)")
    parser.add_argument("--config", default=None, help="Path to config YAML")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    logger.info("Running stage: %s", args.stage)
    STAGES[args.stage](cfg)
    logger.info("Stage '%s' finished.", args.stage)


if __name__ == "__main__":
    main()
