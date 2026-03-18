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

# Per-role model overrides
# Tier 1 — expensive, used sparingly: planner + debugger only
PLANNER_MODEL: str = os.getenv("PLANNER_MODEL", "claude-opus-4-6")
DEBUGGER_MODEL: str = os.getenv("DEBUGGER_MODEL", "claude-opus-4-6")
# Tier 2 — mid-tier: deep research synthesis
BUILDER_MODEL: str = os.getenv("BUILDER_MODEL", "claude-sonnet-4-6")
VERIFIER_MODEL: str = os.getenv("VERIFIER_MODEL", "claude-sonnet-4-6")
REPORTER_MODEL: str = os.getenv("REPORTER_MODEL", "claude-sonnet-4-6")
# Tier 3 — fast/cheap: preliminary runs and search loops
PRELIM_MODEL: str = os.getenv("PRELIM_MODEL", "llama-3.3-70b-versatile")  # Groq, free tier
SEARCH_WORKER_MODEL: str = os.getenv("SEARCH_WORKER_MODEL", "llama-3.3-70b-versatile")  # Groq

# OpenAI
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
QUAL_BUILDER_MODEL: str = os.getenv("QUAL_BUILDER_MODEL", "gpt-4o")   # was gpt-5.4 — 20x cheaper
QUANT_BUILDER_MODEL: str = os.getenv("QUANT_BUILDER_MODEL", "claude-sonnet-4-6")

# Groq — OpenAI-compatible, free tier, very fast (used for preliminary runs + search workers)
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"

# DeepSeek — OpenAI-compatible, very cheap, strong at code/data (~$0.28/1M tokens)
DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

# Collaborative session — how many back-and-forth turns between qual and quant per cycle
SESSION_COLLAB_TURNS: int = int(os.getenv("SESSION_COLLAB_TURNS", "3"))

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

# Time budget — if set, agents calibrate depth to finish within the budget
# Set as a human string e.g. "5m", "2h", "20h" or bare minutes e.g. "120"
TIME_BUDGET: str = os.getenv("TIME_BUDGET", "")  # empty = unlimited

# Slack bot user ID — used by listener to filter out the bot's own messages
SLACK_BOT_USER_ID: str = os.getenv("SLACK_BOT_USER_ID", "")


def set_reports_dir(path: str | Path) -> Path:
    """Update the active reports directory for the current process."""
    global REPORTS_DIR
    REPORTS_DIR = Path(path)
    os.environ["REPORTS_DIR"] = str(REPORTS_DIR)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return REPORTS_DIR
