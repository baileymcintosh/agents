"""Base class shared by all agent roles."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import time

import anthropic
from loguru import logger

from agentorg import config
from agentorg.tools.search import SEARCH_TOOL_DEFINITION, web_search, format_search_results


class BaseAgent(ABC):
    """
    All agents inherit from this class.

    Responsibilities:
    - Load a role-specific system prompt from agent_docs/<role>.md
    - Call Claude with web search tool use enabled
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
        self.use_search = bool(config.TAVILY_API_KEY)

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
        """
        Send a message to Claude with web search tool use enabled.
        Claude will automatically call web_search as many times as needed,
        and we execute those calls and return results until Claude is done.
        """
        content = f"{extra_context}\n\n{user_message}" if extra_context else user_message
        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]

        tools = [SEARCH_TOOL_DEFINITION] if self.use_search else []

        if self.use_search:
            logger.info(f"[{self.role}] → Claude ({self.model}) with web search enabled")
        else:
            logger.info(f"[{self.role}] → Claude ({self.model}) — no web search (TAVILY_API_KEY not set)")

        # Agentic loop: keep running until Claude stops using tools
        while True:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "system": self.system_prompt,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools

            # Retry up to 5 times on rate limit errors with exponential backoff
            response = None
            for attempt in range(5):
                try:
                    response = self.client.messages.create(**kwargs)
                    break
                except anthropic.RateLimitError as e:
                    wait = 60 * (2 ** attempt)  # 60s, 120s, 240s, 480s, 960s
                    logger.warning(f"[{self.role}] Rate limited — waiting {wait}s before retry {attempt + 1}/5")
                    time.sleep(wait)
                    if attempt == 4:
                        raise e
            assert response is not None

            # If Claude is done (no more tool calls), return the text
            if response.stop_reason == "end_turn":
                text_blocks = [b.text for b in response.content if hasattr(b, "text")]
                return "\n\n".join(text_blocks)

            # If Claude wants to use tools, execute them and continue
            if response.stop_reason == "tool_use":
                # Add Claude's response to message history
                messages.append({"role": "assistant", "content": response.content})

                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        if tool_name == "web_search":
                            query = tool_input.get("query", "")
                            max_results = tool_input.get("max_results", 8)
                            logger.info(f"[{self.role}] Web search: '{query}'")
                            results = web_search(query, max_results=max_results)
                            result_text = format_search_results(results)
                        else:
                            result_text = f"Unknown tool: {tool_name}"

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        })

                # Add tool results to message history and loop
                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            logger.warning(f"[{self.role}] Unexpected stop_reason: {response.stop_reason}")
            text_blocks = [b.text for b in response.content if hasattr(b, "text")]
            return "\n\n".join(text_blocks)

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
| Web Search | {"Enabled" if self.use_search else "Disabled — set TAVILY_API_KEY to enable"} |

---

"""
        report_path.write_text(header + content, encoding="utf-8")
        logger.info(f"[{self.role}] Report → {report_path.name}")
        return report_path

    def generate_slack_brief(self, full_report: str) -> str:
        """Ask Claude to write a genuinely informative 2-sentence Slack update."""
        prompt = (
            f"The {self.role} agent just finished work. "
            "Write exactly 2 sentences for a Slack update to a senior executive. "
            "Sentence 1: What specifically was found or accomplished — name actual facts, topics, findings. "
            "Sentence 2: The single most important or surprising insight. "
            "Be specific. No filler. No process commentary.\n\n"
            f"Report:\n{full_report[:3000]}"
        )
        try:
            response = self.client.messages.create(
                model=config.REPORTER_MODEL,
                max_tokens=150,
                messages=[{"role": "user", "content": prompt}],
            )
            return str(response.content[0].text).strip()  # type: ignore[union-attr]
        except Exception:
            return "Work completed — see full report for details."

    def run_with_recovery(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Run the agent with inline debugger recovery.
        On failure, hands off to Debugger to attempt a fix and retry.
        Up to 3 attempts before escalating to Slack.
        """
        prompt_override: str | None = None
        last_error: Exception | None = None

        for attempt in range(1, 4):
            try:
                if prompt_override:
                    result = self._run_with_prompt_override(prompt_override, dry_run)
                else:
                    result = self.run(dry_run=dry_run)
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"[{self.role}] Attempt {attempt} failed: {e}")

                if dry_run:
                    raise

                from agentorg.agents.debugger import DebuggerAgent
                debugger = DebuggerAgent()
                decision = debugger.consult(
                    agent_role=self.role,
                    error=e,
                    original_prompt=prompt_override or "",
                    attempt=attempt,
                )

                if decision["action"] == "retry":
                    prompt_override = decision.get("modified_prompt", "")
                    continue

                # Escalate
                self.write_report(
                    "Agent Failure",
                    f"## {self.role.capitalize()} failed after {attempt} attempts\n\n"
                    f"**Error:** {type(last_error).__name__}: {last_error}\n\n"
                    f"**Debugger:** {decision.get('message', '')}"
                )
                raise RuntimeError(decision.get("message", str(last_error)))

        raise RuntimeError(f"{self.role} failed after 3 attempts: {last_error}")

    def _run_with_prompt_override(self, modified_prompt: str, dry_run: bool) -> dict[str, Any]:
        """Run using a debugger-provided modified prompt."""
        if dry_run:
            return {"status": "dry_run"}
        content = self.call_claude(modified_prompt)
        report_path = self.write_report("Recovery Attempt", content)
        return {"status": "ok", "report": str(report_path)}

    def post_slack_progress(self, emoji: str, status: str, detail: str = "") -> None:
        """Post a progress update to Slack if configured. Never crashes."""
        if not config.SLACK_BOT_TOKEN or not config.SLACK_EXECUTIVE_CHANNEL_ID:
            return
        try:
            from agentorg.slack_bot.client import SlackClient
            slack = SlackClient()
            slack.post_progress(
                channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                emoji=emoji,
                agent=self.role.capitalize(),
                status=status,
                detail=detail,
            )
        except Exception as e:
            logger.warning(f"[{self.role}] Slack progress update failed (non-fatal): {e}")

    @abstractmethod
    def run(self, dry_run: bool = False) -> dict[str, Any]:
        """Execute the agent's primary task. Returns a result summary dict."""
        ...
