.PHONY: install test lint typecheck check run clean

install:  ## Editable install with dev extras
	pip install -e ".[dev]"

test:  ## Run the test suite with coverage
	pytest

lint:  ## Lint with ruff
	ruff check src tests

format:  ## Auto-format with ruff
	ruff format src tests
	ruff check --fix src tests

typecheck:  ## Static type check with mypy (strict)
	mypy

check: lint typecheck test  ## Run every gate CI runs

run:  ## Example run (requires ANTHROPIC_API_KEY)
	sector-research "electric vehicle charging networks"

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage \
	       build dist *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
