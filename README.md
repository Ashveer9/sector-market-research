# Sector Market Research — End-to-End Data Engineering Pipeline

> **Portfolio Project · Enterprise-Grade Data Engineering**
> 
> A production-ready ETL/ELT pipeline that ingests global retail sales data, transforms it through a Medallion Architecture (Bronze → Silver → Gold), loads a Star Schema into DuckDB, and surfaces KPI analytics — all orchestrated by Apache Airflow and validated by a comprehensive test suite.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   SECTOR MARKET RESEARCH PIPELINE                        │
│                                                                          │
│  ┌──────────┐    ┌─────────────────────────────────────────────────┐    │
│  │  Source  │    │              MEDALLION ARCHITECTURE              │    │
│  │          │    │                                                  │    │
│  │  Kaggle  │───▶│  BRONZE          SILVER           GOLD          │    │
│  │  Global  │    │  ────────        ────────         ────────      │    │
│  │  Super-  │    │  Raw CSV   ───▶  Cleansed   ───▶  Star Schema  │    │
│  │  store   │    │  Parquet         Parquet          DuckDB        │    │
│  │  Dataset │    │  (Immutable)     (Validated)      (Curated)     │    │
│  └──────────┘    └─────────────────────────────────────────────────┘    │
│                                    │                                     │
│                                    ▼                                     │
│                  ┌─────────────────────────────────┐                    │
│                  │         ANALYTICS LAYER          │                    │
│                  │  KPI Reports · Sector Analysis   │                    │
│                  │  Market Rankings · Trend Reports │                    │
│                  └─────────────────────────────────┘                    │
│                                                                          │
│  ORCHESTRATION: Apache Airflow 2.8   WAREHOUSE: DuckDB                  │
│  TRANSFORMS:    dbt-duckdb            QUALITY:  Custom Validators        │
│  CONTAINERS:    Docker Compose        CI/CD:    GitHub Actions           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Data Model — Star Schema (Gold Layer)

```
                    ┌──────────────────┐
                    │    dim_date      │
                    │  ─────────────  │
                    │  date_key (PK)  │
                    │  full_date      │
                    │  year           │
                    │  quarter        │
                    │  month          │
                    │  week           │
                    └────────┬─────────┘
                             │
┌──────────────┐    ┌────────┴──────────┐    ┌────────────────────┐
│ dim_customer │    │   fact_orders     │    │   dim_product      │
│ ──────────── │    │  ─────────────── │    │  ────────────────  │
│ customer_key │◀───│  order_key (PK)  │───▶│  product_key (PK)  │
│ customer_id  │    │  date_key (FK)   │    │  product_id        │
│ customer_name│    │  customer_key(FK)│    │  product_name      │
│ segment      │    │  product_key(FK) │    │  category          │
└──────────────┘    │  geo_key (FK)    │    │  sub_category      │
                    │  ship_key (FK)   │    └────────────────────┘
┌──────────────┐    │  ─────────────── │
│ dim_geography│    │  sales           │    ┌────────────────────┐
│ ──────────── │    │  quantity        │    │  dim_ship_mode     │
│ geo_key (PK) │◀───│  discount        │    │  ────────────────  │
│ country      │    │  profit          │───▶│  ship_key (PK)     │
│ city         │    │  shipping_cost   │    │  ship_mode         │
│ state        │    │  profit_margin   │    └────────────────────┘
│ region       │    └───────────────────┘
│ market       │
└──────────────┘
```

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Ingestion | Python + PyArrow | CSV → Parquet (Bronze) |
| Transformation | Pandas + DuckDB | Data cleansing (Silver) |
| Warehouse | DuckDB 0.10 | Star schema (Gold) |
| SQL Models | dbt-duckdb | Declarative transforms |
| Orchestration | Apache Airflow 2.8 | Pipeline scheduling |
| Data Quality | Custom validators + Great Expectations | Validation rules |
| Testing | Pytest | Unit + integration tests |
| Containerisation | Docker + Docker Compose | Reproducible environment |
| CI/CD | GitHub Actions | Automated testing & linting |
| Visualisation | Plotly + pandas | KPI dashboards |

## Dataset

**Source**: [Global Superstore Orders](https://www.kaggle.com/datasets/apoorvaappz/global-super-store-dataset) — Kaggle  
**Domain**: Retail sector market research across global markets  
**Volume**: ~52,000 orders · 24 columns · 2011–2014  
**Markets**: US, EU, APAC, LATAM, Africa, EMEA, Canada

### Key Columns

| Column | Type | Description |
|--------|------|-------------|
| `order_id` | STRING | Unique order identifier |
| `order_date` | DATE | Date order was placed |
| `market` | STRING | Global market segment |
| `segment` | STRING | Customer segment (Consumer/Corporate/Home Office) |
| `category` | STRING | Product category |
| `sub_category` | STRING | Product sub-category |
| `sales` | DECIMAL | Revenue from order line |
| `profit` | DECIMAL | Profit from order line |
| `discount` | DECIMAL | Discount applied (0–1) |

## Project Structure

```
sector-market-research/
├── .github/workflows/          # CI/CD pipelines
│   └── ci.yml
├── airflow/
│   └── dags/
│       └── sector_market_pipeline.py  # Main Airflow DAG
├── dbt/
│   ├── dbt_project.yml
│   ├── models/
│   │   ├── staging/            # stg_* models (source → typed)
│   │   ├── intermediate/       # int_* models (business logic)
│   │   └── marts/              # dim_* + fact_* models
│   └── tests/                  # Custom dbt tests
├── src/
│   ├── ingestion/              # Data ingestion from source
│   ├── bronze/                 # Raw layer loader
│   ├── silver/                 # Cleansing + validation
│   ├── gold/                   # Star schema builder
│   └── analytics/              # KPI engine
├── tests/
│   ├── unit/                   # Unit tests per module
│   └── integration/            # End-to-end pipeline tests
├── scripts/
│   ├── generate_sample_data.py # Generates synthetic Kaggle data
│   ├── run_pipeline.py         # Local pipeline runner
│   └── setup_db.py             # DuckDB schema setup
├── data/                       # Gitignored — created at runtime
├── docker-compose.yml          # Airflow + services
├── Dockerfile                  # Pipeline image
├── requirements.txt
└── config.yaml                 # Central configuration
```

## Quick Start

### Option 1 — Local (no Docker)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate sample data (mimics Kaggle Global Superstore)
python scripts/generate_sample_data.py

# 3. Run the full pipeline
python scripts/run_pipeline.py

# 4. Run dbt transformations
cd dbt && dbt run && dbt test

# 5. Run the test suite
pytest tests/ -v
```

### Option 2 — Docker Compose (with Airflow)

```bash
# 1. Copy environment variables
cp .env.example .env

# 2. Start all services
docker-compose up -d

# 3. Access Airflow UI → http://localhost:8080
#    Login: admin / admin

# 4. Trigger the DAG: sector_market_research_pipeline
```

## Pipeline Stages

```
[1] INGEST     → Download/read CSV from source
[2] BRONZE     → Write raw Parquet (immutable, partitioned by market)
[3] VALIDATE   → Data quality checks (nulls, ranges, uniqueness)
[4] SILVER     → Cleanse, cast types, deduplicate
[5] GOLD       → Build star schema in DuckDB
[6] DBT RUN    → Apply SQL transformation models
[7] DBT TEST   → Run data quality assertions
[8] ANALYTICS  → Compute KPIs and export reports
[9] NOTIFY     → Log pipeline summary
```

## KPI Reports Generated

| Report | Location | Description |
|--------|----------|-------------|
| `sector_performance.csv` | `data/analytics/` | Sales & profit by market + category |
| `segment_analysis.csv` | `data/analytics/` | Revenue by customer segment |
| `top_products.csv` | `data/analytics/` | Top 20 products by profit margin |
| `regional_trends.csv` | `data/analytics/` | QoQ growth by region |
| `discount_impact.csv` | `data/analytics/` | Discount vs profit correlation |

## Data Quality Rules

| Check | Layer | Rule |
|-------|-------|------|
| Null check | Silver | `order_id`, `order_date`, `sales` must not be null |
| Range check | Silver | `discount` ∈ [0, 1], `sales` > 0 |
| Uniqueness | Silver | `order_id` + `product_id` must be unique |
| Referential | Gold | All FK values must exist in dimension tables |
| Freshness | Gold | Max `order_date` must be within expected range |

## Running Tests

```bash
# All tests
pytest tests/ -v --tb=short

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage report
pytest tests/ --cov=src --cov-report=html
```

## CI/CD Pipeline

GitHub Actions runs on every push/PR:
1. **Lint** — `ruff` + `black` code style checks  
2. **Type check** — `mypy` static analysis  
3. **Unit tests** — Fast, no external dependencies  
4. **Integration tests** — Full pipeline with sample data  
5. **dbt compile** — Validates SQL models  

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for development workflow.

---

*Built to demonstrate enterprise-grade data engineering practices: Medallion Architecture, dimensional modelling, orchestration, data quality, containerisation, and CI/CD.*
