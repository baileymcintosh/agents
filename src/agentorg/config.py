"""Central configuration — reads from environment variables / .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Repository root (two levels up from this file: src/agentorg/config.py → root)
ROOT_DIR = Path(__file__).parent.parent.parent

REPORTS_DIR = Path(os.getenv("REPORTS_DIR", str(ROOT_DIR / "reports")))
DATA_DIR = ROOT_DIR / "data"
AGENT_DOCS_DIR = ROOT_DIR / "agent_docs"

# Anthropic
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "claude-sonnet-4-6")
AGENT_MAX_TOKENS: int = int(os.getenv("AGENT_MAX_TOKENS", "8000"))

# Per-role model overrides — defaults shown, override via environment variables
PLANNER_MODEL: str = os.getenv("PLANNER_MODEL", "claude-opus-4-6")
BUILDER_MODEL: str = os.getenv("BUILDER_MODEL", "claude-opus-4-6")
VERIFIER_MODEL: str = os.getenv("VERIFIER_MODEL", "claude-sonnet-4-6")
REPORTER_MODEL: str = os.getenv("REPORTER_MODEL", "claude-sonnet-4-6")

# Slack
SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_SIGNING_SECRET: str = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_EXECUTIVE_CHANNEL_ID: str = os.getenv("SLACK_EXECUTIVE_CHANNEL_ID", "")
SLACK_ENGINEERING_CHANNEL_ID: str = os.getenv("SLACK_ENGINEERING_CHANNEL_ID", "")
SLACK_ALERTS_CHANNEL_ID: str = os.getenv("SLACK_ALERTS_CHANNEL_ID", "")

# GitHub
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO: str = os.getenv("GITHUB_REPO", "")

# Web Search (Tavily — https://tavily.com, free tier available)
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

# Reporting
PDF_EXPORT_ENABLED: bool = os.getenv("PDF_EXPORT_ENABLED", "true").lower() == "true"

# Fast mode — all agents use Sonnet, reduced token limits, skip PDF, one-job pipeline
FAST_MODE: bool = os.getenv("FAST_MODE", "false").lower() == "true"
FAST_MAX_TOKENS: int = int(os.getenv("FAST_MAX_TOKENS", "1200"))

# Slack bot user ID — used by listener to filter out the bot's own messages
SLACK_BOT_USER_ID: str = os.getenv("SLACK_BOT_USER_ID", "")
