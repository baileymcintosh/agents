"""Tests for agent base functionality."""

from __future__ import annotations

import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentorg.agents.base import BaseAgent


class ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing the base class."""
    role = "test_agent"

    def run(self, dry_run: bool = False) -> dict:
        return {"status": "ok"}


@pytest.fixture
def agent(temp_dir: Path) -> ConcreteAgent:
    """Create a test agent with a temporary reports directory."""
    with patch("agentorg.config.REPORTS_DIR", temp_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"):
        return ConcreteAgent()


def test_agent_creates_reports_dir(temp_dir: Path) -> None:
    reports_dir = temp_dir / "reports"
    with patch("agentorg.config.REPORTS_DIR", reports_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"):
        ConcreteAgent()
    assert reports_dir.exists()


def test_agent_loads_system_prompt_from_file(temp_dir: Path) -> None:
    prompt_file = temp_dir / "test_agent.md"
    prompt_file.write_text("You are a test agent.", encoding="utf-8")

    with patch("agentorg.config.REPORTS_DIR", temp_dir), \
         patch("agentorg.config.AGENT_DOCS_DIR", temp_dir), \
         patch("agentorg.config.ANTHROPIC_API_KEY", "test-key"):
        a = ConcreteAgent()

    assert a.system_prompt == "You are a test agent."


def test_agent_uses_fallback_prompt_when_no_file(agent: ConcreteAgent) -> None:
    assert "test_agent" in agent.system_prompt


def test_write_report_creates_file(agent: ConcreteAgent) -> None:
    report_path = agent.write_report("Test Report", "## Content\nSome content here.")
    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Test Report" in content
    assert "Some content here." in content


def test_write_report_filename_includes_role(agent: ConcreteAgent) -> None:
    report_path = agent.write_report("My Report", "content")
    assert "test_agent" in report_path.name


def test_write_report_filename_includes_timestamp(agent: ConcreteAgent) -> None:
    report_path = agent.write_report("My Report", "content")
    today = datetime.date.today().strftime("%Y%m%d")
    assert today in report_path.name
