# ogrep Development Makefile
# Usage: make <target>

.PHONY: help install install-dev test lint fmt check clean build

# Default target
help:
	@echo "ogrep Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install      - Install ogrep in editable mode"
	@echo "  make install-dev  - Install with dev dependencies"
	@echo ""
	@echo "Development:"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linters (ruff, yamllint)"
	@echo "  make fmt          - Format code (ruff format)"
	@echo "  make check        - Run all checks (lint + test)"
	@echo "  make typecheck    - Run mypy type checking"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean        - Remove build artifacts"
	@echo "  make build        - Build distribution package"
	@echo ""
	@echo "Pre-commit:"
	@echo "  make hooks        - Install pre-commit hooks"
	@echo "  make pre-commit   - Run pre-commit on all files"

# =============================================================================
# Setup
# =============================================================================

install:
	pip install -e ./ogrep-marketplace

install-dev:
	pip install -e "./ogrep-marketplace[dev]"

hooks:
	pre-commit install

# =============================================================================
# Development
# =============================================================================

test:
	cd ogrep-marketplace && pytest

test-cov:
	cd ogrep-marketplace && pytest --cov=ogrep --cov-report=term-missing

lint:
	ruff check ogrep-marketplace/ogrep ogrep-marketplace/tests
	yamllint -c .yamllint.yaml .

fmt:
	ruff format ogrep-marketplace/ogrep ogrep-marketplace/tests
	ruff check --fix ogrep-marketplace/ogrep ogrep-marketplace/tests

typecheck:
	cd ogrep-marketplace && mypy ogrep

check: lint test

pre-commit:
	pre-commit run --all-files

# =============================================================================
# Maintenance
# =============================================================================

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name build -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

build: clean
	cd ogrep-marketplace && python -m build

# =============================================================================
# Validation
# =============================================================================

validate-syntax:
	python -m compileall ogrep-marketplace/ogrep

validate-cli:
	ogrep --help
	ogrep index --help
	ogrep query --help
	ogrep reset --help
	ogrep reindex --help
	ogrep clean --help
	ogrep status --help
