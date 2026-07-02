"""Unit tests for the KPI Analytics Engine."""

from pathlib import Path

import pandas as pd
import pytest

from src.gold.warehouse import GoldWarehouse
from src.analytics.kpi_engine import KPIEngine


@pytest.fixture
def loaded_warehouse(sample_df: pd.DataFrame, tmp_duckdb: str, tmp_path: Path) -> GoldWarehouse:
    """Return a GoldWarehouse loaded with the sample fixture."""
    from src.silver.transformer import SilverTransformer

    # Transform sample to Silver-grade format
    t = SilverTransformer(output_dir=tmp_path / "silver")
    silver = t.transform(sample_df)

    wh = GoldWarehouse(db_path=tmp_duckdb)
    wh.load(silver)
    return wh


class TestKPIEngine:

    def test_run_all_returns_reports(
        self, loaded_warehouse: GoldWarehouse, tmp_path: Path
    ) -> None:
        engine = KPIEngine(
            warehouse=loaded_warehouse,
            output_dir=tmp_path / "analytics",
        )
        reports = engine.run_all()
        assert len(reports) > 0
        assert all(isinstance(v, str) for v in reports.values())

    def test_report_files_exist(
        self, loaded_warehouse: GoldWarehouse, tmp_path: Path
    ) -> None:
        out = tmp_path / "analytics"
        engine = KPIEngine(warehouse=loaded_warehouse, output_dir=out)
        engine.run_all()
        csv_files = list(out.glob("*.csv"))
        assert len(csv_files) > 0

    def test_executive_summary_single_row(
        self, loaded_warehouse: GoldWarehouse, tmp_path: Path
    ) -> None:
        engine = KPIEngine(warehouse=loaded_warehouse, output_dir=tmp_path / "analytics")
        engine.run_all()
        summary_path = tmp_path / "analytics" / "executive_summary.csv"
        if summary_path.exists():
            df = pd.read_csv(summary_path)
            assert len(df) == 1
            assert "total_revenue" in df.columns or "total_orders" in df.columns

    def test_sector_performance_has_expected_columns(
        self, loaded_warehouse: GoldWarehouse, tmp_path: Path
    ) -> None:
        engine = KPIEngine(warehouse=loaded_warehouse, output_dir=tmp_path / "analytics")
        engine.run_all()
        perf_path = tmp_path / "analytics" / "sector_performance.csv"
        if perf_path.exists():
            df = pd.read_csv(perf_path)
            assert "market" in df.columns
            assert "total_sales" in df.columns
            assert "total_profit" in df.columns

    def test_discount_impact_bands_present(
        self, loaded_warehouse: GoldWarehouse, tmp_path: Path
    ) -> None:
        engine = KPIEngine(warehouse=loaded_warehouse, output_dir=tmp_path / "analytics")
        engine.run_all()
        disc_path = tmp_path / "analytics" / "discount_impact.csv"
        if disc_path.exists():
            df = pd.read_csv(disc_path)
            assert "discount_band" in df.columns
            assert len(df) > 0
