"""
Integration tests: end-to-end pipeline execution with generated sample data.
These tests run the full Bronze → Silver → Gold → Analytics flow.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="module")
def generated_csv(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a small sample CSV for integration tests."""
    out = tmp_path_factory.mktemp("data") / "test_data.csv"
    result = subprocess.run(
        [sys.executable, "scripts/generate_sample_data.py", "--rows", "200", "--output", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"Data generation failed: {result.stderr}"
    assert out.exists()
    return out


@pytest.fixture(scope="module")
def pipeline_result(generated_csv: Path, tmp_path_factory: pytest.TempPathFactory) -> dict:
    """Run the full pipeline and return the result dict."""
    import os
    tmp = tmp_path_factory.mktemp("pipeline")

    # Override config paths via env
    env_overrides = {
        "DUCKDB_PATH": str(tmp / "warehouse.duckdb"),
    }
    original = {k: os.environ.get(k) for k in env_overrides}
    os.environ.update(env_overrides)

    # Monkey-patch config singleton paths for isolation
    from src.utils.config import Config
    Config._instance = None  # Reset singleton

    import src.utils.config as cfg_module
    cfg_module.config._data["paths"]["db"] = str(tmp / "warehouse.duckdb")
    cfg_module.config._data["paths"]["raw"] = str(tmp / "raw")
    cfg_module.config._data["paths"]["processed"] = str(tmp / "processed")
    cfg_module.config._data["paths"]["analytics"] = str(tmp / "analytics")

    from src.ingestion.ingestor import Ingestor
    from src.bronze.raw_layer import BronzeWriter
    from src.silver.transformer import SilverTransformer
    from src.silver.validator import DataValidator
    from src.gold.warehouse import GoldWarehouse
    from src.analytics.kpi_engine import KPIEngine

    # Stage 1: Ingest
    ingestor = Ingestor(source_path=str(generated_csv))
    raw_df, ingest_result = ingestor.ingest()

    # Stage 2: Bronze
    bronze = BronzeWriter(output_dir=tmp / "raw")
    bronze.write(raw_df)

    # Stage 3: Validate
    validator = DataValidator()
    validation_report = validator.validate(raw_df)

    # Stage 4: Silver
    transformer = SilverTransformer(output_dir=tmp / "processed")
    silver_df = transformer.transform(raw_df)
    transformer.write(silver_df)

    # Stage 5: Gold
    warehouse = GoldWarehouse(db_path=str(tmp / "warehouse.duckdb"))
    table_counts = warehouse.load(silver_df)

    # Stage 6: Analytics
    engine = KPIEngine(warehouse=warehouse, output_dir=tmp / "analytics")
    reports = engine.run_all()

    # Restore env
    for k, v in original.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    return {
        "raw_df": raw_df,
        "ingest_result": ingest_result,
        "validation_report": validation_report,
        "silver_df": silver_df,
        "table_counts": table_counts,
        "reports": reports,
        "warehouse": warehouse,
        "analytics_dir": tmp / "analytics",
    }


class TestEndToEndPipeline:

    def test_ingestion_reads_expected_columns(self, pipeline_result: dict) -> None:
        df = pipeline_result["raw_df"]
        expected = ["order_id", "sales", "customer_id", "product_id", "market"]
        for col in expected:
            assert col in df.columns, f"Missing column: {col}"

    def test_silver_has_more_columns_than_raw(self, pipeline_result: dict) -> None:
        raw = pipeline_result["raw_df"]
        silver = pipeline_result["silver_df"]
        # Silver adds derived columns (profit_margin, order_year, etc.)
        assert len(silver.columns) > len(raw.columns)

    def test_silver_row_count_reasonable(self, pipeline_result: dict) -> None:
        raw = pipeline_result["raw_df"]
        silver = pipeline_result["silver_df"]
        # Should not drop more than 10% of rows for clean synthetic data
        assert len(silver) >= len(raw) * 0.9

    def test_gold_fact_orders_loaded(self, pipeline_result: dict) -> None:
        counts = pipeline_result["table_counts"]
        assert "fact_orders" in counts
        assert counts["fact_orders"] > 0

    def test_gold_all_dimensions_loaded(self, pipeline_result: dict) -> None:
        counts = pipeline_result["table_counts"]
        required_tables = [
            "dim_customer", "dim_product", "dim_date",
            "dim_geography", "dim_ship_mode",
        ]
        for table in required_tables:
            assert table in counts, f"Missing dimension: {table}"
            assert counts[table] > 0, f"Empty dimension: {table}"

    def test_fact_orders_references_valid_customers(self, pipeline_result: dict) -> None:
        wh = pipeline_result["warehouse"]
        result = wh.query("""
            SELECT COUNT(*) AS orphan_count
            FROM gold.fact_orders f
            LEFT JOIN gold.dim_customer c ON f.customer_key = c.customer_key
            WHERE c.customer_key IS NULL
        """)
        assert result["orphan_count"].iloc[0] == 0

    def test_analytics_reports_generated(self, pipeline_result: dict) -> None:
        reports = pipeline_result["reports"]
        assert len(reports) >= 5

    def test_sector_performance_report_not_empty(self, pipeline_result: dict) -> None:
        path = pipeline_result["analytics_dir"] / "sector_performance.csv"
        assert path.exists(), "sector_performance.csv not found"
        df = pd.read_csv(path)
        assert len(df) > 0
        assert "total_sales" in df.columns

    def test_executive_summary_totals_positive(self, pipeline_result: dict) -> None:
        path = pipeline_result["analytics_dir"] / "executive_summary.csv"
        assert path.exists()
        df = pd.read_csv(path)
        assert df["total_revenue"].iloc[0] > 0
        assert df["total_orders"].iloc[0] > 0

    def test_validation_ran_all_rules(self, pipeline_result: dict) -> None:
        report = pipeline_result["validation_report"]
        assert len(report.results) >= 5
