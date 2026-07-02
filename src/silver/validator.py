"""
Data quality validator: enforces business rules on the Silver layer.
Returns a structured ValidationReport with pass/fail per rule.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from src.utils.config import config
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RuleResult:
    rule_name: str
    column: str
    passed: bool
    details: str
    failed_count: int = 0
    total_count: int = 0

    @property
    def failure_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.failed_count / self.total_count


@dataclass
class ValidationReport:
    dataset: str
    total_rows: int
    results: list[RuleResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failed_rules(self) -> list[RuleResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "total_rows": self.total_rows,
            "rules_passed": sum(1 for r in self.results if r.passed),
            "rules_failed": len(self.failed_rules),
            "overall_passed": self.passed,
            "failed_rules": [
                {"rule": r.rule_name, "column": r.column, "details": r.details}
                for r in self.failed_rules
            ],
        }


class DataValidator:
    """Runs configurable data quality checks against a DataFrame."""

    def __init__(self) -> None:
        self.null_threshold: float = config.get(
            "data_quality", "null_threshold", default=0.05
        )
        self.duplicate_threshold: float = config.get(
            "data_quality", "duplicate_threshold", default=0.01
        )
        self.critical_columns: list[str] = config.get(
            "data_quality", "critical_columns", default=[]
        )
        self.range_checks: dict[str, list[float]] = config.get(
            "data_quality", "range_checks", default={}
        )

    def validate(self, df: pd.DataFrame, dataset: str = "orders") -> ValidationReport:
        """Run all validation rules and return a consolidated report."""
        logger.info("Running data quality checks on %d rows...", len(df))
        report = ValidationReport(dataset=dataset, total_rows=len(df))

        for col in self.critical_columns:
            if col in df.columns:
                report.results.append(self._check_nulls(df, col))

        for col, (low, high) in self.range_checks.items():
            if col in df.columns:
                report.results.append(self._check_range(df, col, low, high))

        report.results.append(self._check_duplicates(df))
        report.results.append(self._check_date_column(df, "order_date"))
        report.results.append(self._check_positive_sales(df))

        passed = sum(1 for r in report.results if r.passed)
        total = len(report.results)
        logger.info(
            "Validation complete: %d/%d rules passed%s",
            passed,
            total,
            " ✓" if report.passed else " ✗ (see failed rules)",
        )

        if not report.passed:
            for rule in report.failed_rules:
                logger.warning("FAILED [%s] %s: %s", rule.column, rule.rule_name, rule.details)

        return report

    def _check_nulls(self, df: pd.DataFrame, col: str) -> RuleResult:
        null_count = df[col].isna().sum()
        rate = null_count / len(df) if len(df) else 0.0
        passed = rate <= self.null_threshold
        return RuleResult(
            rule_name="null_check",
            column=col,
            passed=passed,
            details=f"{null_count} nulls ({rate:.1%}) — threshold {self.null_threshold:.1%}",
            failed_count=null_count,
            total_count=len(df),
        )

    def _check_range(
        self, df: pd.DataFrame, col: str, low: float, high: float
    ) -> RuleResult:
        numeric = pd.to_numeric(df[col], errors="coerce")
        out_of_range = ((numeric < low) | (numeric > high)).sum()
        passed = out_of_range == 0
        return RuleResult(
            rule_name="range_check",
            column=col,
            passed=passed,
            details=f"{out_of_range} values outside [{low}, {high}]",
            failed_count=int(out_of_range),
            total_count=len(df),
        )

    def _check_duplicates(self, df: pd.DataFrame) -> RuleResult:
        key_cols = [c for c in ["order_id", "product_id"] if c in df.columns]
        if not key_cols:
            return RuleResult("duplicate_check", "order_id+product_id", True, "Key columns absent")

        dup_count = df.duplicated(subset=key_cols).sum()
        rate = dup_count / len(df) if len(df) else 0.0
        passed = rate <= self.duplicate_threshold
        return RuleResult(
            rule_name="duplicate_check",
            column="+".join(key_cols),
            passed=passed,
            details=f"{dup_count} duplicates ({rate:.1%}) — threshold {self.duplicate_threshold:.1%}",
            failed_count=int(dup_count),
            total_count=len(df),
        )

    @staticmethod
    def _check_date_column(df: pd.DataFrame, col: str) -> RuleResult:
        if col not in df.columns:
            return RuleResult("date_format_check", col, True, "Column absent — skipped")

        parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=False)
        invalid = parsed.isna().sum()
        passed = invalid == 0
        return RuleResult(
            rule_name="date_format_check",
            column=col,
            passed=passed,
            details=f"{invalid} unparseable dates",
            failed_count=int(invalid),
            total_count=len(df),
        )

    @staticmethod
    def _check_positive_sales(df: pd.DataFrame) -> RuleResult:
        if "sales" not in df.columns:
            return RuleResult("positive_sales_check", "sales", True, "Column absent — skipped")

        numeric = pd.to_numeric(df["sales"], errors="coerce")
        neg_count = (numeric <= 0).sum()
        passed = neg_count == 0
        return RuleResult(
            rule_name="positive_sales_check",
            column="sales",
            passed=passed,
            details=f"{neg_count} rows with sales ≤ 0",
            failed_count=int(neg_count),
            total_count=len(df),
        )
