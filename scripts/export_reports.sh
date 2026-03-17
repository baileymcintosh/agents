#!/usr/bin/env bash
# scripts/export_reports.sh — Export all Markdown reports to PDF
set -euo pipefail

OUTPUT_DIR=${1:-reports/}

echo "=== Exporting reports to PDF ==="
echo "Output directory: $OUTPUT_DIR"

uv run agentorg export --format pdf --out "$OUTPUT_DIR"

echo ""
echo "=== Export complete ==="
ls -lh "$OUTPUT_DIR"*.pdf 2>/dev/null || echo "No PDF files found."
