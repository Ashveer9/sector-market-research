.PHONY: help setup install data pipeline eda segment churn basket cohort test lint clean

PY ?= python3

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

setup: ## Install runtime + dev dependencies and the package (editable)
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e .

install: ## Install runtime dependencies only
	$(PY) -m pip install -r requirements.txt

data: ## Download raw data and build the cleaned dataset
	$(PY) -m sector_research.pipeline clean

pipeline: ## Run the full end-to-end pipeline
	$(PY) -m sector_research.pipeline all

eda: ## Run exploratory data analysis
	$(PY) -m sector_research.pipeline eda

segment: ## Run customer segmentation
	$(PY) -m sector_research.pipeline segment

cohort: ## Run cohort retention analysis
	$(PY) -m sector_research.pipeline cohort

basket: ## Run market-basket analysis
	$(PY) -m sector_research.pipeline basket

churn: ## Train and evaluate the churn model
	$(PY) -m sector_research.pipeline churn

test: ## Run the test suite
	$(PY) -m pytest

lint: ## Lint with ruff
	$(PY) -m ruff check src tests

clean: ## Remove generated data, models and caches (keeps figures/reports)
	rm -rf data/interim/* data/processed/* models/*.joblib
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
