"""
Qualitative Builder Agent — powered by OpenAI GPT-4o.

Role: Global affairs analyst / policy researcher.
- Reads news reports, speeches, statements, analyst opinions
- Builds narrative context around geopolitical events
- Answers quantitative partner's questions with sourced explanations
- Asks quantitative partner to verify claims in the data
"""

from __future__ import annotations

import datetime
import json
import time
from pathlib import Path
from typing import Any

from loguru import logger

from agentorg import config
from agentorg.messaging import AgentMessage, AgentMessenger
from agentorg.tools.search import web_search, format_search_results


# OpenAI tool definition for web search
_SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for current news, analysis, official statements, and reports. "
            "Use multiple targeted queries. Prefer primary sources: Reuters, Bloomberg, "
            "AP, official government/central bank statements, think tanks (IISS, CFR, Brookings)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "max_results": {"type": "integer", "description": "Number of results (default 8)", "default": 8},
            },
            "required": ["query"],
        },
    },
}


class QualBuilderAgent:
    """OpenAI-based qualitative research agent."""

    role = "qual_builder"

    def __init__(self) -> None:
        import openai
        self.client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        self.model = config.QUAL_BUILDER_MODEL
        self.reports_dir = config.REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt = self._load_system_prompt()
        self.use_search = bool(config.TAVILY_API_KEY)
        self._all_findings: list[str] = []

    def _load_system_prompt(self) -> str:
        prompt_path = config.AGENT_DOCS_DIR / "qual_builder.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are a senior global affairs analyst and policy researcher. "
            "Your role is to gather and synthesize qualitative intelligence: "
            "news reports, official statements, speeches, expert opinions, and historical context. "
            "You work alongside a quantitative data scientist who spots anomalies in market data — "
            "your job is to provide the narrative explanation behind the numbers."
        )

    def call_openai(self, user_message: str, max_searches: int = 8) -> str:
        """Run OpenAI with web search tool use loop."""
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        tools = [_SEARCH_TOOL] if self.use_search else []
        search_count = 0

        logger.info(f"[qual] → OpenAI ({self.model})")

        while True:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "system", "content": self.system_prompt}] + messages,
                "max_tokens": 4096,
            }
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = "auto"

            for attempt in range(4):
                try:
                    response = self.client.chat.completions.create(**kwargs)
                    break
                except Exception as e:
                    if "rate" in str(e).lower() and attempt < 3:
                        wait = 30 * (2 ** attempt)
                        logger.warning(f"[qual] Rate limited — waiting {wait}s")
                        time.sleep(wait)
                    else:
                        raise

            choice = response.choices[0]

            if choice.finish_reason == "stop":
                return choice.message.content or ""

            if choice.finish_reason == "tool_calls":
                messages.append({"role": "assistant", "content": choice.message.content, "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in (choice.message.tool_calls or [])
                ]})

                tool_results = []
                for tc in (choice.message.tool_calls or []):
                    if tc.function.name == "web_search":
                        if search_count >= max_searches:
                            result = "Search limit reached. Synthesize what you have."
                        else:
                            args = json.loads(tc.function.arguments)
                            query = args.get("query", "")
                            n = args.get("max_results", 8)
                            logger.info(f"[qual] Web search ({search_count + 1}/{max_searches}): '{query}'")
                            results = web_search(query, max_results=n)
                            result = format_search_results(results)
                            search_count += 1
                    else:
                        result = f"Unknown tool: {tc.function.name}"

                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                messages.extend(tool_results)
                continue

            # Unexpected finish reason
            return choice.message.content or ""

    def run_turn(
        self,
        turn: int,
        research_plan: str,
        messenger: AgentMessenger,
        completed_sections: list[str],
        clock_context: str = "",
    ) -> str:
        """Execute one research turn. Returns findings as markdown string."""

        # Drain messages from quant partner
        inbound = messenger.drain("qual")
        partner_context = messenger.format_for_prompt(inbound) if inbound else ""

        # Build prompt
        prompt_parts = []

        if clock_context:
            prompt_parts.append(clock_context)

        prompt_parts.append(
            f"## Your Research Task — Turn {turn}\n\n"
            f"You are the qualitative researcher in a collaborative session. "
            f"Your quantitative partner is simultaneously analyzing market data.\n\n"
            f"**Research Plan:**\n{research_plan}\n\n"
            f"**Sections already covered:** {', '.join(completed_sections) if completed_sections else 'None yet'}\n"
        )

        if partner_context:
            prompt_parts.append(
                f"\n{partner_context}\n\n"
                "Address your partner's questions directly with sourced evidence before continuing your own research."
            )

        prompt_parts.append(
            "\n## Instructions\n"
            "1. Search for the most current primary sources on your assigned topics.\n"
            "2. Answer any questions from your quantitative partner with specific sourced evidence.\n"
            "3. If you find something that should appear in the data (price moves, volume spikes, "
            "regime changes affecting markets), flag it to your partner.\n"
            "4. Write your findings in structured markdown with clear headings.\n"
            "5. End your response with a `## Questions for Quant` section if you have data questions.\n"
            "   Format: 'Check [asset/metric] around [date/period] — I'm seeing [event] that should show up.'\n"
        )

        prompt = "\n\n".join(prompt_parts)

        findings = self.call_openai(prompt, max_searches=8)
        self._all_findings.append(findings)

        # Extract and post any questions/findings for the quant builder
        self._extract_and_post_messages(findings, messenger)

        return findings

    def _extract_and_post_messages(self, text: str, messenger: AgentMessenger) -> None:
        """Parse the agent's output for cross-agent messages and post them."""
        lines = text.split("\n")
        in_questions = False
        question_lines: list[str] = []

        for line in lines:
            ll = line.lower()
            if "## questions for quant" in ll or "**questions for quant**" in ll:
                in_questions = True
                continue
            if in_questions:
                if line.startswith("##") and "questions for quant" not in ll:
                    break  # new section, stop
                if line.strip():
                    question_lines.append(line.strip())

        if question_lines:
            content = "\n".join(question_lines)
            messenger.post("qual", "quant", "question", content)

    def write_report(self, turn: int, content: str) -> Path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self.role}_turn{turn:02d}.md"
        report_path = self.reports_dir / filename
        header = (
            f"# Qualitative Research — Turn {turn}\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| Agent | Qual Builder (OpenAI {self.model}) |\n"
            f"| Date | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n\n---\n\n"
        )
        report_path.write_text(header + content, encoding="utf-8")
        logger.info(f"[qual] Report → {report_path.name}")
        return report_path

    def write_consolidated_report(self) -> Path:
        """Write a single report consolidating all turns."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self.role}_consolidated.md"
        report_path = self.reports_dir / filename
        header = (
            f"# Qualitative Research — Consolidated ({len(self._all_findings)} turns)\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| Agent | Qual Builder (OpenAI {self.model}) |\n"
            f"| Date | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n\n---\n\n"
        )
        body = "\n\n---\n\n".join(
            f"## Turn {i + 1}\n\n{f}" for i, f in enumerate(self._all_findings)
        )
        report_path.write_text(header + body, encoding="utf-8")
        logger.info(f"[qual] Consolidated report → {report_path.name}")
        return report_path


    def run(self, dry_run: bool = False) -> dict:
        """Run a single research turn — used by CLI."""
        if dry_run:
            return {"status": "dry_run"}
        brief_path = config.REPORTS_DIR.parent / "BRIEF.md"
        if not brief_path.exists():
            brief_path = config.ROOT_DIR / "BRIEF.md"
        brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else "Research the assigned topic thoroughly."
        report = self.run_turn(brief)
        return {"status": "ok", "report": str(report)}

    def run_with_recovery(self, dry_run: bool = False) -> dict:
        """Compatibility shim — calls run()."""
        return self.run(dry_run=dry_run)
