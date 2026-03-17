#!/usr/bin/env bash
# scripts/setup.sh — First-time developer setup
set -euo pipefail

echo "=== AgentOrg Setup ==="

# Check for uv
if ! command -v uv &>/dev/null; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "Installing Python dependencies..."
uv sync --extra dev

echo "Setting up .env..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "  Created .env from .env.example"
  echo "  ⚠️  Edit .env and add your API keys before running agents."
else
  echo "  .env already exists — skipping."
fi

echo "Creating data directories..."
mkdir -p data/raw data/processed data/external data/cache

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys (ANTHROPIC_API_KEY, SLACK_BOT_TOKEN, etc.)"
echo "  2. Run tests:  bash scripts/test.sh"
echo "  3. Run an agent:  uv run agentorg run planner --dry-run"
