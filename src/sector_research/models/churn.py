"""Customer churn prediction.

**Problem framing.** We split the observation window at a cutoff
``max_date - inactivity_days``. Behavioural features are engineered from
transactions *before* the cutoff; the label is whether the customer made *any*
purchase in the holdout window *after* the cutoff. This temporal design
prevents target leakage — we only ever predict the future from the past.

Two models are compared (a transparent logistic-regression baseline and a
gradient-boosted ensemble); the stronger one by ROC-AUC is persisted.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..config import Config, get_logger
from ..features.rfm import build_customer_features
from ..viz.theme import PALETTE, apply_theme, savefig

logger = get_logger(__name__)


def build_churn_frame(df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Construct the supervised churn table (features pre-cutoff, label post-cutoff)."""
    inactivity = int(cfg["churn"]["inactivity_days"])
    max_date = df["invoice_date"].max()
    cutoff = max_date - pd.Timedelta(days=inactivity)

    pre = df[df["invoice_date"] <= cutoff]
    post = df[df["invoice_date"] > cutoff]

    # Features are built as-of the cutoff (recency relative to cutoff).
    feats = build_customer_features(pre, cfg, snapshot=cutoff + pd.Timedelta(days=1))

    active_after = set(post["customer_id"].unique())
    feats["churned"] = (~feats["customer_id"].isin(active_after)).astype(int)
    logger.info(
        "Churn frame: %s customers active before %s; churn rate %.1f%% over the next %s days",
        f"{len(feats):,}", cutoff.date(), 100 * feats["churned"].mean(), inactivity,
    )
    return feats, cutoff


def train_churn(df: pd.DataFrame, cfg: Config) -> dict:
    """Train, evaluate and persist the churn model; return a metrics dict."""
    fig_dir = cfg.path(cfg["paths"]["figures"])
    model_dir = cfg.path(cfg["paths"]["models"])
    fig_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    feats, cutoff = build_churn_frame(df, cfg)
    features = cfg["churn"]["features"]
    X = feats[features].fillna(0.0)
    y = feats["churned"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=cfg["churn"]["test_size"],
        random_state=cfg.random_state, stratify=y,
    )

    candidates = {
        "logistic_regression": Pipeline(
            [("scale", StandardScaler()),
             ("clf", LogisticRegression(max_iter=1000, class_weight="balanced"))]
        ),
        "gradient_boosting": GradientBoostingClassifier(random_state=cfg.random_state),
    }

    results = {}
    for name, model in candidates.items():
        model.fit(X_train, y_train)
        proba = model.predict_proba(X_test)[:, 1]
        results[name] = {
            "model": model,
            "roc_auc": float(roc_auc_score(y_test, proba)),
            "pr_auc": float(average_precision_score(y_test, proba)),
            "proba": proba,
        }
        logger.info("  %-20s ROC-AUC=%.3f  PR-AUC=%.3f",
                    name, results[name]["roc_auc"], results[name]["pr_auc"])

    best_name = max(results, key=lambda n: results[n]["roc_auc"])
    best = results[best_name]
    best_model = best["model"]
    proba = best["proba"]
    preds = (proba >= 0.5).astype(int)

    _plot_roc(y_test, results, fig_dir)
    importances = _feature_importance(best_model, features, fig_dir, best_name)

    model_path = model_dir / "churn_model.joblib"
    joblib.dump({"model": best_model, "features": features, "cutoff": str(cutoff.date())}, model_path)

    report = classification_report(y_test, preds, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_test, preds)
    metrics = {
        "best_model": best_name,
        "roc_auc": best["roc_auc"],
        "pr_auc": best["pr_auc"],
        "precision_churn": float(report["1"]["precision"]),
        "recall_churn": float(report["1"]["recall"]),
        "f1_churn": float(report["1"]["f1-score"]),
        "accuracy": float(report["accuracy"]),
        "churn_rate": float(y.mean()),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "confusion_matrix": cm.tolist(),
        "top_feature": importances.index[0] if len(importances) else None,
        "model_path": str(model_path),
    }
    logger.info("Best model: %s (ROC-AUC=%.3f). Saved to %s", best_name, best["roc_auc"], model_path)
    return metrics


def _plot_roc(y_test, results: dict, fig_dir: Path) -> None:
    apply_theme()
    fig, ax = plt.subplots()
    for i, (name, res) in enumerate(results.items()):
        fpr, tpr, _ = roc_curve(y_test, res["proba"])
        ax.plot(fpr, tpr, color=PALETTE[i], lw=2,
                label=f"{name} (AUC={res['roc_auc']:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.legend(loc="lower right")
    savefig(fig, fig_dir / "07_churn_roc.png", "Churn Model — ROC Curves")


def _feature_importance(model, features: list[str], fig_dir: Path, name: str) -> pd.Series:
    """Extract and plot feature importance (tree gain or |coef|)."""
    if hasattr(model, "feature_importances_"):
        imp = pd.Series(model.feature_importances_, index=features)
    elif isinstance(model, Pipeline) and hasattr(model[-1], "coef_"):
        imp = pd.Series(np.abs(model[-1].coef_[0]), index=features)
    else:
        return pd.Series(dtype=float)

    imp = imp.sort_values(ascending=False)
    apply_theme()
    fig, ax = plt.subplots()
    top = imp.iloc[::-1]
    ax.barh(top.index, top.values, color=PALETTE[3])
    ax.set_xlabel("Importance")
    savefig(fig, fig_dir / "08_churn_feature_importance.png",
            f"Churn Drivers — {name.replace('_', ' ').title()}")
    return imp


def run_churn(df: pd.DataFrame, cfg: Config) -> dict:
    """Public entry point used by the pipeline orchestrator."""
    return train_churn(df, cfg)
