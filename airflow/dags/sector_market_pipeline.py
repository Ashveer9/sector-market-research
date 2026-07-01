"""
Airflow DAG: Sector Market Research Data Pipeline

Orchestrates the full Medallion Architecture pipeline:
  ingest → bronze → validate → silver → gold → dbt → analytics

Schedule: Daily at 06:00 UTC
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.utils.trigger_rule import TriggerRule

# Ensure project src is importable inside Airflow workers
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Default args ──────────────────────────────────────────────────────────────

DEFAULT_ARGS = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}

# ── Task functions ─────────────────────────────────────────────────────────────

def task_ingest(**ctx) -> dict:
    from src.ingestion.ingestor import Ingestor
    ingestor = Ingestor()
    df, result = ingestor.ingest()
    ctx["ti"].xcom_push(key="rows_ingested", value=result.rows_read)
    ctx["ti"].xcom_push(key="ingest_success", value=result.success)
    if not result.success:
        raise ValueError(f"Ingestion failed: {result.error}")
    return {"rows_ingested": result.rows_read, "file_hash": result.file_hash}


def task_write_bronze(**ctx) -> str:
    import pandas as pd
    from src.bronze.raw_layer import BronzeWriter
    from src.ingestion.ingestor import Ingestor

    ingestor = Ingestor()
    df, _ = ingestor.ingest()

    bronze = BronzeWriter()
    path = bronze.write(df)
    return str(path)


def task_validate(**ctx) -> dict:
    from src.bronze.raw_layer import BronzeWriter
    from src.silver.validator import DataValidator

    bronze = BronzeWriter()
    df = bronze.read()

    validator = DataValidator()
    report = validator.validate(df)

    ctx["ti"].xcom_push(key="validation_passed", value=report.passed)
    ctx["ti"].xcom_push(key="validation_summary", value=report.summary())

    if not report.passed:
        failed_rules = [r.rule_name for r in report.failed_rules]
        raise ValueError(f"Data quality check failed: {failed_rules}")

    return report.summary()


def task_check_quality_gate(**ctx) -> str:
    """Branch: route to silver transform if validation passed, else to alert."""
    passed = ctx["ti"].xcom_pull(key="validation_passed", task_ids="validate")
    return "transform_silver" if passed else "quality_alert"


def task_transform_silver(**ctx) -> dict:
    from src.bronze.raw_layer import BronzeWriter
    from src.silver.transformer import SilverTransformer

    bronze = BronzeWriter()
    df = bronze.read()

    transformer = SilverTransformer()
    silver_df = transformer.transform(df)
    path = transformer.write(silver_df)

    ctx["ti"].xcom_push(key="silver_rows", value=len(silver_df))
    return {"rows": len(silver_df), "path": str(path)}


def task_load_gold(**ctx) -> dict:
    from src.silver.transformer import SilverTransformer
    from src.gold.warehouse import GoldWarehouse

    transformer = SilverTransformer()
    silver_df = transformer.read()

    warehouse = GoldWarehouse()
    counts = warehouse.load(silver_df)
    return counts


def task_generate_kpis(**ctx) -> dict:
    from src.analytics.kpi_engine import KPIEngine
    from src.gold.warehouse import GoldWarehouse

    warehouse = GoldWarehouse()
    engine = KPIEngine(warehouse=warehouse)
    reports = engine.run_all()
    return {"reports": list(reports.keys()), "count": len(reports)}


def task_quality_alert(**ctx) -> None:
    summary = ctx["ti"].xcom_pull(key="validation_summary", task_ids="validate")
    raise RuntimeError(f"Pipeline halted due to data quality failures: {summary}")


def task_pipeline_summary(**ctx) -> None:
    ti = ctx["ti"]
    rows_in = ti.xcom_pull(key="rows_ingested", task_ids="ingest")
    rows_silver = ti.xcom_pull(key="silver_rows", task_ids="transform_silver")

    print(f"""
╔══════════════════════════════════════════════╗
║     SECTOR MARKET RESEARCH PIPELINE          ║
║     Run: {ctx['ds']}                         ║
╠══════════════════════════════════════════════╣
║  Rows Ingested  : {rows_in:>8}              ║
║  Rows → Silver  : {rows_silver:>8}          ║
╚══════════════════════════════════════════════╝
    """)


# ── DAG definition ────────────────────────────────────────────────────────────

with DAG(
    dag_id="sector_market_research_pipeline",
    description="End-to-end Medallion Architecture pipeline for sector market research",
    default_args=DEFAULT_ARGS,
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    tags=["data-engineering", "etl", "medallion", "sector-research"],
    doc_md="""
# Sector Market Research Pipeline

Implements a full Bronze → Silver → Gold Medallion Architecture.

## Stages
1. **Ingest** — Read CSV from source
2. **Bronze** — Write raw Parquet (immutable)
3. **Validate** — Data quality gate
4. **Silver** — Cleanse and type-cast
5. **Gold** — Build DuckDB Star Schema
6. **dbt** — SQL transformation models
7. **Analytics** — KPI report generation
    """,
) as dag:

    start = EmptyOperator(task_id="start")

    ingest = PythonOperator(
        task_id="ingest",
        python_callable=task_ingest,
    )

    write_bronze = PythonOperator(
        task_id="write_bronze",
        python_callable=task_write_bronze,
    )

    validate = PythonOperator(
        task_id="validate",
        python_callable=task_validate,
    )

    quality_gate = BranchPythonOperator(
        task_id="quality_gate",
        python_callable=task_check_quality_gate,
    )

    quality_alert = PythonOperator(
        task_id="quality_alert",
        python_callable=task_quality_alert,
    )

    transform_silver = PythonOperator(
        task_id="transform_silver",
        python_callable=task_transform_silver,
    )

    load_gold = PythonOperator(
        task_id="load_gold",
        python_callable=task_load_gold,
    )

    run_dbt = BashOperator(
        task_id="run_dbt",
        bash_command=(
            "cd /opt/airflow/dags/../../../dbt && "
            "dbt run --profiles-dir . && dbt test --profiles-dir ."
        ),
    )

    generate_kpis = PythonOperator(
        task_id="generate_kpis",
        python_callable=task_generate_kpis,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    pipeline_summary = PythonOperator(
        task_id="pipeline_summary",
        python_callable=task_pipeline_summary,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
    )

    end = EmptyOperator(task_id="end", trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS)

    # ── Dependencies ──────────────────────────────────────────────────────
    (
        start
        >> ingest
        >> write_bronze
        >> validate
        >> quality_gate
        >> [transform_silver, quality_alert]
    )
    transform_silver >> load_gold >> run_dbt >> generate_kpis
    [generate_kpis, quality_alert] >> pipeline_summary >> end
