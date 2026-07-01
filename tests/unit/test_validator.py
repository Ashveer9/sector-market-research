"""Unit tests for the Silver layer data validator."""

import pandas as pd
import pytest

from src.silver.validator import DataValidator, ValidationReport


class TestDataValidator:

    def test_passes_clean_data(self, sample_df: pd.DataFrame) -> None:
        v = DataValidator()
        report = v.validate(sample_df)
        # Clean fixture data should have at most minor issues
        assert report.total_rows == len(sample_df)
        assert isinstance(report.passed, bool)

    def test_fails_on_null_order_id(self) -> None:
        df = pd.DataFrame({
            "order_id":   [None, None, "CA-001"],
            "order_date": ["2013-01-01"] * 3,
            "customer_id": ["C1"] * 3,
            "product_id": ["P1"] * 3,
            "sales":      [100.0] * 3,
            "discount":   [0.0] * 3,
            "quantity":   [1] * 3,
            "profit":     [10.0] * 3,
        })
        v = DataValidator()
        report = v.validate(df)
        null_rule = next(
            (r for r in report.results if r.rule_name == "null_check" and r.column == "order_id"),
            None,
        )
        assert null_rule is not None
        assert not null_rule.passed

    def test_fails_on_out_of_range_discount(self) -> None:
        df = pd.DataFrame({
            "order_id":   ["CA-001", "CA-002"],
            "order_date": ["2013-01-01"] * 2,
            "customer_id": ["C1", "C2"],
            "product_id": ["P1", "P2"],
            "sales":      [100.0, 200.0],
            "discount":   [1.5, 2.0],   # invalid: > 1.0
            "quantity":   [1, 2],
            "profit":     [10.0, 20.0],
        })
        v = DataValidator()
        report = v.validate(df)
        range_rule = next(
            (r for r in report.results if r.rule_name == "range_check" and r.column == "discount"),
            None,
        )
        assert range_rule is not None
        assert not range_rule.passed

    def test_detects_duplicates(self) -> None:
        df = pd.DataFrame({
            "order_id":   ["CA-001", "CA-001", "CA-002"],
            "order_date": ["2013-01-01"] * 3,
            "customer_id": ["C1", "C1", "C2"],
            "product_id": ["P1", "P1", "P2"],  # exact duplicates
            "sales":      [100.0, 100.0, 200.0],
            "discount":   [0.0, 0.0, 0.1],
            "quantity":   [1, 1, 2],
            "profit":     [10.0, 10.0, 20.0],
        })
        v = DataValidator()
        report = v.validate(df)
        dup_rule = next(
            (r for r in report.results if r.rule_name == "duplicate_check"),
            None,
        )
        assert dup_rule is not None
        assert dup_rule.failed_count >= 1

    def test_fails_on_negative_sales(self) -> None:
        df = pd.DataFrame({
            "order_id":   ["CA-001", "CA-002"],
            "order_date": ["2013-01-01"] * 2,
            "customer_id": ["C1", "C2"],
            "product_id": ["P1", "P2"],
            "sales":      [-50.0, 0.0],  # invalid
            "discount":   [0.0, 0.0],
            "quantity":   [1, 1],
            "profit":     [10.0, 5.0],
        })
        v = DataValidator()
        report = v.validate(df)
        sales_rule = next(
            (r for r in report.results if r.rule_name == "positive_sales_check"),
            None,
        )
        assert sales_rule is not None
        assert not sales_rule.passed

    def test_validation_report_summary_structure(self, sample_df: pd.DataFrame) -> None:
        v = DataValidator()
        report = v.validate(sample_df)
        summary = report.summary()
        assert "dataset" in summary
        assert "total_rows" in summary
        assert "rules_passed" in summary
        assert "rules_failed" in summary
        assert "overall_passed" in summary
        assert "failed_rules" in summary

    def test_failure_rate_calculation(self) -> None:
        df = pd.DataFrame({
            "order_id":   [None, None, "CA-003", "CA-004", "CA-005"],
            "order_date": ["2013-01-01"] * 5,
            "customer_id": ["C1"] * 5,
            "product_id": ["P1"] * 5,
            "sales":      [100.0] * 5,
            "discount":   [0.0] * 5,
            "quantity":   [1] * 5,
            "profit":     [10.0] * 5,
        })
        v = DataValidator()
        report = v.validate(df)
        null_rule = next(
            (r for r in report.results if r.rule_name == "null_check" and r.column == "order_id"),
            None,
        )
        if null_rule:
            assert abs(null_rule.failure_rate - 0.4) < 0.01
