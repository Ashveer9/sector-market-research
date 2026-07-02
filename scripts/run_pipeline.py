"""
Local pipeline runner — executes the full ETL pipeline end-to-end.

Usage:
    python scripts/run_pipeline.py [--skip-dbt] [--source path/to/file.csv]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analytics.kpi_engine import KPIEngine
from src.bronze.raw_layer import BronzeWriter
from src.gold.warehouse import GoldWarehouse
from src.ingestion.ingestor import Ingestor
from src.silver.transformer import SilverTransformer
from src.silver.validator import DataValidator
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(source: str | None = None, skip_dbt: bool = False) -> dict:
    """Execute the full Medallion Architecture pipeline."""
    run_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    start = time.time()
    results: dict = {"run_id": run_id, "stages": {}}

    logger.info("=" * 60)
    logger.info("PIPELINE START  run_id=%s", run_id)
    logger.info("=" * 60)

    # ── Stage 1: Ingest ──────────────────────────────────────────────────
    logger.info("[1/7] INGEST — Reading source data")
    t0 = time.time()
    ingestor = Ingestor(source_path=source)
    raw_df, ingest_result = ingestor.ingest()
    results["stages"]["ingest"] = {
        "rows": ingest_result.rows_read,
        "columns": len(ingest_result.columns_found),
        "duration_s": round(time.time() - t0, 2),
        "success": ingest_result.success,
    }

    # ── Stage 2: Bronze ──────────────────────────────────────────────────
    logger.info("[2/7] BRONZE — Writing raw Parquet")
    t0 = time.time()
    bronze = BronzeWriter()
    bronze_path = bronze.write(raw_df)
    results["stages"]["bronze"] = {
        "path": str(bronze_path),
        "rows": len(raw_df),
        "duration_s": round(time.time() - t0, 2),
    }

    # ── Stage 3: Validate ────────────────────────────────────────────────
    logger.info("[3/7] VALIDATE — Running data quality checks")
    t0 = time.time()
    validator = DataValidator()
    report = validator.validate(raw_df)
    results["stages"]["validate"] = {
        **report.summary(),
        "duration_s": round(time.time() - t0, 2),
    }
    if not report.passed:
        logger.warning("Data quality issues found — pipeline continues with warnings")

    # ── Stage 4: Silver ──────────────────────────────────────────────────
    logger.info("[4/7] SILVER — Transforming and cleansing data")
    t0 = time.time()
    transformer = SilverTransformer()
    silver_df = transformer.transform(raw_df)
    silver_path = transformer.write(silver_df)
    results["stages"]["silver"] = {
        "path": str(silver_path),
        "rows": len(silver_df),
        "duration_s": round(time.time() - t0, 2),
    }

    # ── Stage 5: Gold ─────────────────────────────────────────────────────
    logger.info("[5/7] GOLD — Building Star Schema in DuckDB")
    t0 = time.time()
    warehouse = GoldWarehouse()
    table_counts = warehouse.load(silver_df)
    results["stages"]["gold"] = {
        "table_counts": table_counts,
        "duration_s": round(time.time() - t0, 2),
    }

    # ── Stage 6: dbt ──────────────────────────────────────────────────────
    if not skip_dbt:
        logger.info("[6/7] DBT — Running SQL transformation models")
        t0 = time.time()
        dbt_result = _run_dbt()
        results["stages"]["dbt"] = {**dbt_result, "duration_s": round(time.time() - t0, 2)}
    else:
        logger.info("[6/7] DBT — Skipped (--skip-dbt)")
        results["stages"]["dbt"] = {"skipped": True}

    # ── Stage 7: Analytics ───────────────────────────────────────────────
    logger.info("[7/7] ANALYTICS — Generating KPI reports")
    t0 = time.time()
    kpi = KPIEngine(warehouse=warehouse)
    reports = kpi.run_all()
    results["stages"]["analytics"] = {
        "reports_generated": list(reports.keys()),
        "output_dir": str(Path("data/analytics")),
        "duration_s": round(time.time() - t0, 2),
    }

    # ── Summary ───────────────────────────────────────────────────────────
    total = round(time.time() - start, 2)
    results["total_duration_s"] = total
    results["success"] = all(
        s.get("success", True) for s in results["stages"].values()
        if isinstance(s, dict)
    )

    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE  run_id=%s  duration=%.1fs", run_id, total)
    logger.info("Gold table counts: %s", table_counts)
    logger.info("Reports: %s", list(reports.keys()))
    logger.info("=" * 60)

    # Write run manifest
    manifest_path = Path("data") / f"pipeline_run_{run_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info("Run manifest: %s", manifest_path)

    return results


def _run_dbt() -> dict:
    """Run dbt models if dbt is available."""
    dbt_dir = Path(__file__).parent.parent / "dbt"
    if not dbt_dir.exists():
        return {"skipped": True, "reason": "dbt/ directory not found"}

    try:
        result = subprocess.run(
            ["dbt", "run", "--profiles-dir", str(dbt_dir), "--project-dir", str(dbt_dir)],
            capture_output=True, text=True, timeout=120
        )
        test_result = subprocess.run(
            ["dbt", "test", "--profiles-dir", str(dbt_dir), "--project-dir", str(dbt_dir)],
            capture_output=True, text=True, timeout=120
        )
        return {
            "run_returncode": result.returncode,
            "test_returncode": test_result.returncode,
            "success": result.returncode == 0 and test_result.returncode == 0,
        }
    except FileNotFoundError:
        return {"skipped": True, "reason": "dbt not installed"}
    except subprocess.TimeoutExpired:
        return {"skipped": True, "reason": "dbt timed out"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Sector Market Research Pipeline Runner")
    parser.add_argument("--source", type=str, default=None, help="Path to source CSV")
    parser.add_argument("--skip-dbt", action="store_true", help="Skip dbt models")
    args = parser.parse_args()

    results = run_pipeline(source=args.source, skip_dbt=args.skip_dbt)
    sys.exit(0 if results.get("success") else 1)


if __name__ == "__main__":
    main()
