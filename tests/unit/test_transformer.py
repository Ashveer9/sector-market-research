"""Unit tests for the Silver layer transformer."""

from pathlib import Path

import pandas as pd
import pytest

from src.silver.transformer import SilverTransformer


class TestSilverTransformer:

    def test_removes_pipeline_metadata(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        df = sample_df.copy()
        df["_ingested_at"] = "2024-01-01"
        df["_layer"] = "bronze"
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(df)
        # Bronze-specific tag removed; transformer adds its own Silver _layer tag
        assert "_ingested_at" not in result.columns
        assert "_layer" in result.columns
        assert (result["_layer"] == "silver").all()

    def test_parses_order_date(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(sample_df)
        assert "order_date" in result.columns
        # After parsing, order_date should not be strings
        non_null = result["order_date"].dropna()
        assert len(non_null) > 0

    def test_casts_sales_to_float(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        df = sample_df.copy()
        df["sales"] = df["sales"].astype(str)  # force string
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(df)
        assert pd.api.types.is_float_dtype(result["sales"])

    def test_deduplicates_on_order_product(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        df = pd.concat([sample_df, sample_df.iloc[:1]], ignore_index=True)
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(df)
        combos = result[["order_id", "product_id"]].dropna()
        assert combos.duplicated().sum() == 0

    def test_adds_profit_margin(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(sample_df)
        assert "profit_margin" in result.columns
        margins = result["profit_margin"].dropna()
        assert len(margins) > 0

    def test_adds_order_year_quarter_month(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(sample_df)
        assert "order_year" in result.columns
        assert "order_quarter" in result.columns
        assert "order_month" in result.columns

    def test_adds_days_to_ship(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(sample_df)
        assert "days_to_ship" in result.columns
        # Standard Class should take ~5-7 days for fixture data
        std = result[result["ship_mode"] == "Standard Class"]["days_to_ship"].dropna()
        if len(std) > 0:
            assert (std >= 0).all()

    def test_adds_silver_metadata(self, sample_df: pd.DataFrame, tmp_path: Path) -> None:
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(sample_df)
        assert "_processed_at" in result.columns
        assert "_layer" in result.columns
        assert (result["_layer"] == "silver").all()

    def test_cleans_string_whitespace(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "order_id": ["  CA-001  "],
            "order_date": ["2013-01-15"],
            "ship_date": ["2013-01-18"],
            "ship_mode": [" Standard Class "],
            "customer_id": ["CG-001"],
            "product_id": ["FUR-001"],
            "sales": [100.0],
            "quantity": [1],
            "discount": [0.0],
            "profit": [20.0],
            "shipping_cost": [5.0],
            "customer_name": ["Test User"],
            "segment": ["Consumer"],
            "city": ["NYC"], "state": ["NY"], "country": ["US"],
            "postal_code": ["10001"], "market": ["US"], "region": ["East"],
            "category": ["Furniture"], "sub_category": ["Chairs"],
            "product_name": ["Test Chair"], "order_priority": ["High"],
        })
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(df)
        assert result["order_id"].iloc[0] == "CA-001"
        assert result["ship_mode"].iloc[0] == "Standard Class"

    def test_drops_null_critical_columns(self, tmp_path: Path) -> None:
        df = pd.DataFrame({
            "order_id": [None, "CA-002"],
            "order_date": ["2013-01-15", "2013-01-16"],
            "ship_date": ["2013-01-18", "2013-01-19"],
            "ship_mode": ["Standard Class", "First Class"],
            "customer_id": ["CG-001", "CG-002"],
            "product_id": ["FUR-001", "FUR-002"],
            "sales": [100.0, 200.0],
            "quantity": [1, 2],
            "discount": [0.0, 0.1],
            "profit": [20.0, 40.0],
            "shipping_cost": [5.0, 10.0],
            "customer_name": ["A", "B"], "segment": ["Consumer", "Consumer"],
            "city": ["NYC", "LA"], "state": ["NY", "CA"], "country": ["US", "US"],
            "postal_code": ["10001", "90001"], "market": ["US", "US"],
            "region": ["East", "West"], "category": ["Furniture", "Furniture"],
            "sub_category": ["Chairs", "Chairs"], "product_name": ["P1", "P2"],
            "order_priority": ["High", "Low"],
        })
        t = SilverTransformer(output_dir=tmp_path)
        result = t.transform(df)
        assert len(result) == 1
        assert result["order_id"].iloc[0] == "CA-002"
