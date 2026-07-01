.PHONY: install setup generate run test lint typecheck dbt-compile dbt-run clean help

# ── Configuration ──────────────────────────────────────────────────────────────
PYTHON     := python3
PIP        := pip3
DATA_ROWS  := 5000
SOURCE_CSV := data/sample/global_superstore.csv

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""

# ── Setup ──────────────────────────────────────────────────────────────────────
install:  ## Install Python dependencies
	$(PIP) install -r requirements.txt

setup: install  ## Full setup: install deps + create directories
	mkdir -p data/{raw,processed,analytics,sample} logs
	cp -n .env.example .env || true
	@echo "✓ Setup complete"

# ── Data ───────────────────────────────────────────────────────────────────────
generate:  ## Generate synthetic sample data (default: 5000 rows)
	$(PYTHON) scripts/generate_sample_data.py --rows $(DATA_ROWS)

# ── Pipeline ───────────────────────────────────────────────────────────────────
run:  ## Run the full ETL pipeline (no dbt)
	$(PYTHON) scripts/run_pipeline.py --source $(SOURCE_CSV) --skip-dbt

run-with-dbt:  ## Run the full ETL pipeline including dbt transforms
	$(PYTHON) scripts/run_pipeline.py --source $(SOURCE_CSV)

pipeline: generate run  ## Generate data then run pipeline

# ── dbt ────────────────────────────────────────────────────────────────────────
dbt-compile:  ## Compile dbt models (validate SQL)
	cd dbt && dbt compile --profiles-dir . --project-dir .

dbt-run:  ## Run dbt transformation models
	cd dbt && dbt run --profiles-dir . --project-dir .

dbt-test:  ## Run dbt data quality tests
	cd dbt && dbt test --profiles-dir . --project-dir .

dbt-docs:  ## Generate and serve dbt documentation
	cd dbt && dbt docs generate --profiles-dir . && dbt docs serve --profiles-dir .

# ── Tests ──────────────────────────────────────────────────────────────────────
test:  ## Run unit + integration tests
	pytest tests/ -v

test-unit:  ## Run unit tests only
	pytest tests/unit/ -v

test-integration:  ## Run integration tests only
	pytest tests/integration/ -v --timeout=120

test-cov:  ## Run tests with HTML coverage report
	pytest tests/ --cov=src --cov-report=html --cov-report=term-missing
	@echo "Coverage report: htmlcov/index.html"

# ── Code quality ───────────────────────────────────────────────────────────────
lint:  ## Run ruff linter
	ruff check src/ scripts/ tests/

lint-fix:  ## Auto-fix ruff lint issues
	ruff check --fix src/ scripts/ tests/

format:  ## Auto-format with black + isort
	black src/ scripts/ tests/
	isort src/ scripts/ tests/

format-check:  ## Check formatting (no changes)
	black --check src/ scripts/ tests/
	isort --check-only src/ scripts/ tests/

typecheck:  ## Run mypy type checker
	mypy src/ --ignore-missing-imports

# ── Docker ─────────────────────────────────────────────────────────────────────
docker-build:  ## Build the pipeline Docker image
	docker build -t sector-market-research:latest .

docker-run:  ## Run the pipeline in Docker
	docker-compose --profile pipeline up pipeline

airflow-up:  ## Start Airflow (webserver + scheduler)
	docker-compose up -d airflow-init airflow-webserver airflow-scheduler
	@echo "Airflow UI: http://localhost:8080 (admin/admin)"

airflow-down:  ## Stop Airflow
	docker-compose down

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:  ## Remove generated data and artifacts
	rm -rf data/{raw,processed,analytics,sample}/*.parquet
	rm -rf data/warehouse.duckdb data/*.json
	rm -rf dbt/target dbt/dbt_packages
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
	rm -rf __pycache__ src/**/__pycache__ tests/**/__pycache__
	@echo "✓ Cleaned"

clean-all: clean  ## Full clean including sample data
	rm -rf data/
	rm -rf logs/
