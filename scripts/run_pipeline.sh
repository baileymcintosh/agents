#!/usr/bin/env bash
# scripts/run_pipeline.sh — Run the full agent pipeline locally (for testing)
set -euo pipefail

DRY_RUN=${1:-""}
FLAG=""
if [ "$DRY_RUN" = "--dry-run" ]; then
  FLAG="--dry-run"
  echo "=== Running pipeline in DRY-RUN mode ==="
else
  echo "=== Running full agent pipeline ==="
fi

echo ""
echo "Step 1/4: Planner..."
uv run agentorg run planner $FLAG

echo ""
echo "Step 2/4: Builder..."
uv run agentorg run builder $FLAG

echo ""
echo "Step 3/4: Verifier..."
uv run agentorg run verifier $FLAG

echo ""
echo "Step 4/4: Reporter..."
uv run agentorg run reporter $FLAG

echo ""
echo "=== Pipeline complete. Reports in reports/ ==="
uv run agentorg status
