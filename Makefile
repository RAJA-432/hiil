.PHONY: help install test test-v test-coverage typecheck lint format format-fix lint-fix check clean clean-all

.DEFAULT_GOAL := help

help: ## List available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install project with dev dependencies
	uv pip install -e ".[dev]"

test: ## Run all tests (quick, fail-fast)
	python -m pytest tests/ -x -q

test-v: ## Run all tests with verbose output
	python -m pytest tests/ -x -v

test-coverage: ## Run tests with coverage report
	python -m pytest tests/ --cov=mcp_cli --cov=setu_bridge --cov=vajra_gate --cov=veda_engine --cov-report=term-missing

typecheck: ## Run mypy static type checking
	python -m mypy mcp_cli setu_bridge veda_engine vajra_gate --ignore-missing-imports

lint: ## Run ruff linter
	python -m ruff check mcp_cli setu_bridge veda_engine vajra_gate tests/

format: ## Check formatting with ruff
	python -m ruff format --check mcp_cli setu_bridge veda_engine vajra_gate tests/

format-fix: ## Auto-format with ruff
	python -m ruff format mcp_cli setu_bridge veda_engine vajra_gate tests/

lint-fix: ## Auto-fix lint issues with ruff
	python -m ruff check --fix mcp_cli setu_bridge veda_engine vajra_gate tests/

check: ## Run lint + typecheck + test in sequence
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test

clean: ## Remove __pycache__, cache dirs, coverage, build artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage *.egg-info build dist

clean-all: ## Also remove .venv and uv.lock
	$(MAKE) clean
	rm -rf .venv uv.lock
