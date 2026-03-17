#!/usr/bin/env bash
# scripts/test.sh — Run all tests, linting, and type checking
set -euo pipefail

echo "=== Linting (ruff) ==="
uv run ruff check src/ tests/

echo ""
echo "=== Format check (ruff) ==="
uv run ruff format --check src/ tests/

echo ""
echo "=== Type check (mypy) ==="
uv run mypy src/

echo ""
echo "=== Tests (pytest) ==="
uv run pytest

echo ""
echo "=== All checks passed ==="
