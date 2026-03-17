"""Base class shared by all agent roles."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import anthropic
from loguru import logger

from agentorg import config


class BaseAgent(ABC):
    """
    All agents inherit from this class.

    Responsibilities:
    - Load a role-specific system prompt from agent_docs/<role>.md
    - Call Claude with that prompt
    - Write a timestamped Markdown report to reports/
    """

    role: str = "base"

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.AGENT_MODEL
        self.max_tokens = config.AGENT_MAX_TOKENS
        self.reports_dir = config.REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = config.AGENT_DOCS_DIR / f"{self.role}.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        logger.warning(f"No system prompt at {prompt_path} — using generic fallback.")
        return (
            f"You are the {self.role} agent in an autonomous research organization. "
            "Perform your role carefully and always write a structured, readable report."
        )

    def call_claude(self, user_message: str, extra_context: str = "") -> str:
        """Send a message to Claude and return the text response."""
        content = f"{extra_context}\n\n{user_message}" if extra_context else user_message
        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]

        logger.info(f"[{self.role}] → Claude ({self.model})")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system_prompt,
            messages=messages,
        )
        return str(response.content[0].text)  # type: ignore[union-attr]

    def write_report(self, title: str, content: str) -> Path:
        """Write a Markdown report and return its path."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = title.lower().replace(" ", "_").replace("/", "-")[:40]
        filename = f"{timestamp}_{self.role}_{slug}.md"
        report_path = self.reports_dir / filename

        header = f"""# {title}

| Field | Value |
|---|---|
| Agent | {self.role.capitalize()} |
| Date | {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")} |
| Model | {self.model} |

---

"""
        report_path.write_text(header + content, encoding="utf-8")
        logger.info(f"[{self.role}] Report → {report_path.name}")
        return report_path

    @abstractmethod
    def run(self, dry_run: bool = False) -> dict[str, Any]:
        """Execute the agent's primary task. Returns a result summary dict."""
        ...
