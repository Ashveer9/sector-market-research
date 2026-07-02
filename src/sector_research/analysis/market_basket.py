"""Market-basket analysis via the Apriori algorithm.

Identifies products frequently purchased together and expresses them as
association rules (support / confidence / lift). These rules drive
cross-sell, bundling and shelf/website placement recommendations.
"""
from __future__ import annotations

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

from ..config import Config, get_logger

logger = get_logger(__name__)


def build_basket(df: pd.DataFrame, country: str) -> pd.DataFrame:
    """One-hot invoice × product matrix for a single market."""
    market = df[df["country"] == country]
    basket = (
        market.groupby(["invoice", "description"])["quantity"].sum().unstack(fill_value=0)
    )
    # Encode presence/absence rather than counts.
    return (basket > 0).astype(bool)


def mine_rules(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Run Apriori and return the top association rules by the configured metric."""
    mb = cfg["market_basket"]
    basket = build_basket(df, mb["country"])
    logger.info("Mining rules on %s baskets × %s products (%s)",
                f"{basket.shape[0]:,}", f"{basket.shape[1]:,}", mb["country"])

    frequent = apriori(
        basket, min_support=mb["min_support"], use_colnames=True, max_len=mb["max_len"]
    )
    if frequent.empty:
        logger.warning("No frequent itemsets at min_support=%.3f", mb["min_support"])
        return pd.DataFrame()

    rules = association_rules(frequent, metric=mb["metric"], min_threshold=mb["min_threshold"])
    rules = rules[rules["antecedents"].apply(len) >= 1]
    rules = rules.sort_values(["lift", "confidence"], ascending=False).reset_index(drop=True)

    # Readable string forms of the itemsets.
    rules["antecedents_str"] = rules["antecedents"].apply(lambda s: ", ".join(sorted(s)))
    rules["consequents_str"] = rules["consequents"].apply(lambda s: ", ".join(sorted(s)))
    cols = ["antecedents_str", "consequents_str", "support", "confidence", "lift"]
    return rules[cols].head(mb["top_n_rules"])


def run_market_basket(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Mine rules and persist them to ``reports/`` as CSV."""
    rules = mine_rules(df, cfg)
    if not rules.empty:
        out = cfg.path(cfg["paths"]["reports"]) / "association_rules.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        rules.to_csv(out, index=False)
        logger.info("Saved %s association rules to %s", len(rules), out)
    return rules
