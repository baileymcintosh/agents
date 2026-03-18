"""Base class shared by all agent roles."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import time

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config
from agentorg.timing import RunClock
from agentorg.tools.search import SEARCH_TOOL_DEFINITION, web_search, format_search_results

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised in minimal test envs
    anthropic = None  # type: ignore[assignment]


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
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY) if anthropic else None
        # Fast mode overrides per-role model with Sonnet and caps tokens
        if config.FAST_MODE:
            self.model = config.REPORTER_MODEL
            self.max_tokens = config.FAST_MAX_TOKENS
        else:
            self.model = config.AGENT_MODEL
            self.max_tokens = config.AGENT_MAX_TOKENS
        self.reports_dir = config.REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt = self._load_system_prompt()
        self.use_search = bool(config.TAVILY_API_KEY)
        self.clock: RunClock | None = RunClock.load()

    def _is_openai_model(self) -> bool:
        return self.model.startswith(("gpt-", "o1", "o3", "o4", "codex"))

    def _is_groq_model(self) -> bool:
        return self.model.startswith(("llama-", "mixtral-", "gemma-", "whisper-")) or "groq" in self.model

    def _is_deepseek_model(self) -> bool:
        return self.model.startswith("deepseek-")

    def _call_openai_compat(self, user_message: str, base_url: str | None, api_key: str, provider: str) -> str:
        """OpenAI-compatible chat completion — works for OpenAI, Groq, DeepSeek."""
        import openai
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        client = openai.OpenAI(**kwargs)
        logger.info(f"[{self.role}] → {provider} ({self.model})")
        for attempt in range(4):
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    max_tokens=self.max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                if "rate" in str(e).lower() and attempt < 3:
                    wait = 30 * (2 ** attempt)
                    logger.warning(f"[{self.role}] {provider} rate limit — waiting {wait}s")
                    time.sleep(wait)
                else:
                    raise
        return ""

    def _call_openai(self, user_message: str) -> str:
        return self._call_openai_compat(user_message, None, config.OPENAI_API_KEY, "OpenAI")

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
        Send a message to the configured model. Routes to OpenAI if self.model is a GPT/o-series model,
        otherwise uses Anthropic Claude with web search tool use.
        """
        content = f"{extra_context}\n\n{user_message}" if extra_context else user_message

        if self._is_openai_model():
            return self._call_openai(content)
        if self._is_groq_model():
            return self._call_openai_compat(content, config.GROQ_BASE_URL, config.GROQ_API_KEY, "Groq")
        if self._is_deepseek_model():
            return self._call_openai_compat(content, config.DEEPSEEK_BASE_URL, config.DEEPSEEK_API_KEY, "DeepSeek")
        if self.client is None or anthropic is None:
            raise RuntimeError("anthropic package is required for Claude-backed agents.")
        messages: list[dict[str, Any]] = [{"role": "user", "content": content}]

        # Inject time context into the message if a budget is active
        if self.clock:
            time_ctx = self.clock.prompt_context(self.role)
            content = time_ctx + "\n\n" + content
            # Dynamically cap max_tokens to the clock's token hint
            token_cap = self.clock.token_hint()
            effective_max_tokens = min(self.max_tokens, token_cap)
        else:
            effective_max_tokens = self.max_tokens

        tools = [SEARCH_TOOL_DEFINITION] if self.use_search else []
        # Search cap: clock-driven if budget set, else 2 in fast mode, else unlimited
        if self.clock:
            max_searches = self.clock.max_searches()
        elif config.FAST_MODE:
            max_searches = 2
        else:
            max_searches = 999
        fast_max_results = 3 if (config.FAST_MODE or bool(self.clock)) else 8
        search_count = 0

        if self.use_search:
            if config.FAST_MODE:
                logger.info(f"[{self.role}] → Claude ({self.model}) — fast mode, web search capped at {max_searches}")
            else:
                logger.info(f"[{self.role}] → Claude ({self.model}) with web search enabled")
        else:
            logger.info(f"[{self.role}] → Claude ({self.model}) — no web search (TAVILY_API_KEY not set)")

        # Agentic loop: keep running until Claude stops using tools
        while True:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": effective_max_tokens,
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
                except Exception as e:
                    if anthropic is None or not isinstance(e, anthropic.RateLimitError):
                        raise
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
                            if search_count >= max_searches:
                                # Search cap reached — tell Claude to wrap up with what it has
                                logger.info(f"[{self.role}] Search cap reached ({max_searches}) — stopping search loop")
                                result_text = "Search limit reached. Write your response now using what you already know."
                            else:
                                query = tool_input.get("query", "")
                                n_results = fast_max_results if config.FAST_MODE else tool_input.get("max_results", 8)
                                logger.info(f"[{self.role}] Web search ({search_count + 1}/{max_searches}): '{query}'")
                                results = web_search(query, max_results=n_results)
                                result_text = format_search_results(results)
                                search_count += 1
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
            if self.client is None:
                return "Work completed — see full report for details."
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
