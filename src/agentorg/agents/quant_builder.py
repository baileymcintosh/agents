"""
Quantitative Builder Agent — powered by Claude with Python execution.

Role: Macro data scientist / quantitative analyst.
- Fetches live market data (yfinance, FRED) and runs analysis
- Generates annotated charts: price history, correlations, historical analogues
- Spots anomalies and asks the qualitative partner for narrative explanations
- Answers qual partner's data verification requests
"""

from __future__ import annotations

import datetime
import time
from pathlib import Path
from typing import Any

import anthropic
from loguru import logger

from agentorg import config
from agentorg.messaging import AgentMessenger
from agentorg.tools.python_exec import PYTHON_EXEC_TOOL_DEFINITION, PythonExecutor
from agentorg.tools.search import SEARCH_TOOL_DEFINITION, web_search, format_search_results


class QuantBuilderAgent:
    """Claude-based quantitative research agent with Python execution capability."""

    role = "quant_builder"

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.QUANT_BUILDER_MODEL
        self.reports_dir = config.REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.system_prompt = self._load_system_prompt()
        self.executor = PythonExecutor(timeout=90)
        self.use_search = bool(config.TAVILY_API_KEY)
        self._all_findings: list[str] = []
        self._all_charts: list[str] = []

    def _load_system_prompt(self) -> str:
        prompt_path = config.AGENT_DOCS_DIR / "quant_builder.md"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")
        return (
            "You are a senior macro data scientist and quantitative analyst. "
            "Your role is to pull live market and economic data, run analysis in Python, "
            "and generate professional annotated charts. "
            "You work alongside a qualitative policy analyst — when you spot anomalies "
            "in the data, ask your partner for the narrative explanation. "
            "When your partner tells you about key events, verify them in the data and annotate your charts."
        )

    def call_claude(self, user_message: str, max_searches: int = 5) -> tuple[str, list[str]]:
        """
        Run Claude with Python execution + web search tools.
        Returns (text_response, list_of_chart_paths).
        """
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        tools = [PYTHON_EXEC_TOOL_DEFINITION]
        if self.use_search:
            tools.append(SEARCH_TOOL_DEFINITION)

        search_count = 0
        all_charts: list[str] = []

        logger.info(f"[quant] → Claude ({self.model}) with Python exec + web search")

        while True:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "max_tokens": config.AGENT_MAX_TOKENS,
                "system": self.system_prompt,
                "messages": messages,
                "tools": tools,
            }

            for attempt in range(5):
                try:
                    response = self.client.messages.create(**kwargs)
                    break
                except anthropic.RateLimitError as e:
                    wait = 60 * (2 ** attempt)
                    logger.warning(f"[quant] Rate limited — waiting {wait}s")
                    time.sleep(wait)
                    if attempt == 4:
                        raise e

            if response.stop_reason == "end_turn":
                text = "\n\n".join(b.text for b in response.content if hasattr(b, "text"))
                return text, all_charts

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})
                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    if block.name == "execute_python":
                        code = block.input.get("code", "")
                        desc = block.input.get("description", "")
                        result = self.executor.run(code, description=desc)
                        all_charts.extend(result.charts)
                        result_text = result.to_tool_result()

                    elif block.name == "web_search":
                        if search_count >= max_searches:
                            result_text = "Search limit reached."
                        else:
                            query = block.input.get("query", "")
                            logger.info(f"[quant] Web search ({search_count + 1}/{max_searches}): '{query}'")
                            results = web_search(query, max_results=5)
                            result_text = format_search_results(results)
                            search_count += 1
                    else:
                        result_text = f"Unknown tool: {block.name}"

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_text,
                    })

                messages.append({"role": "user", "content": tool_results})
                continue

            # Unexpected stop reason
            text = "\n\n".join(b.text for b in response.content if hasattr(b, "text"))
            return text, all_charts

    def run_turn(
        self,
        turn: int,
        research_plan: str,
        messenger: AgentMessenger,
        clock_context: str = "",
    ) -> tuple[str, list[str]]:
        """Execute one research turn. Returns (findings_markdown, chart_paths)."""

        inbound = messenger.drain("quant")
        partner_context = messenger.format_for_prompt(inbound) if inbound else ""

        prompt_parts = []

        if clock_context:
            prompt_parts.append(clock_context)

        prompt_parts.append(
            f"## Your Research Task — Turn {turn}\n\n"
            f"You are the quantitative analyst in a collaborative research session. "
            f"Your qualitative partner is simultaneously researching news and policy.\n\n"
            f"**Research Plan:**\n{research_plan}\n\n"
        )

        if partner_context:
            prompt_parts.append(
                f"\n{partner_context}\n\n"
                "Address your partner's data requests first — verify their events in the market data "
                "and annotate your charts accordingly."
            )

        prompt_parts.append(
            "\n## Instructions\n"
            "1. Fetch live data with yfinance and/or FRED. Use real tickers: "
            "BZ=F (Brent crude), CL=F (WTI), GC=F (Gold), ^GSPC (S&P 500), ^VIX, "
            "TLT (20yr Treasuries). For FRED: 'DCOILBRENTEU', 'CPIAUCSL', 'DGS10'.\n"
            "2. Generate professional charts with:\n"
            "   - Clear title and labelled axes\n"
            "   - Annotated vertical lines for key events (use axvline + text)\n"
            "   - Date range covering the conflict period plus 3-month pre-war baseline\n"
            "3. Run historical comparisons: overlay 1990 Gulf War, 2003 Iraq, 2021 Suez blockage "
            "   on the same chart where relevant.\n"
            "4. Print key statistics to stdout (% change, peak, correlations).\n"
            "5. Call plt.show() after each figure to save it.\n"
            "6. End your response with a `## Questions for Qual` section for anything you see "
            "   in the data that needs a narrative explanation.\n"
            "   Format: 'I see [metric] moved [X%] on [date]. What happened?'\n"
        )

        prompt = "\n\n".join(prompt_parts)
        findings, charts = self.call_claude(prompt)
        self._all_findings.append(findings)
        self._all_charts.extend(charts)

        # Extract and post questions for qual
        self._extract_and_post_messages(findings, messenger)

        return findings, charts

    def _extract_and_post_messages(self, text: str, messenger: AgentMessenger) -> None:
        lines = text.split("\n")
        in_questions = False
        question_lines: list[str] = []

        for line in lines:
            ll = line.lower()
            if "## questions for qual" in ll or "**questions for qual**" in ll:
                in_questions = True
                continue
            if in_questions:
                if line.startswith("##") and "questions for qual" not in ll:
                    break
                if line.strip():
                    question_lines.append(line.strip())

        if question_lines:
            content = "\n".join(question_lines)
            messenger.post("quant", "qual", "question", content)

    def write_report(self, turn: int, content: str, charts: list[str]) -> Path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self.role}_turn{turn:02d}.md"
        report_path = self.reports_dir / filename

        chart_section = ""
        if charts:
            chart_section = "\n\n## Charts Generated\n\n" + "\n".join(
                f"![{Path(c).stem}]({c})" for c in charts
            )

        header = (
            f"# Quantitative Research — Turn {turn}\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| Agent | Quant Builder (Claude {self.model}) |\n"
            f"| Date | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n"
            f"| Charts | {len(charts)} |\n\n---\n\n"
        )
        report_path.write_text(header + content + chart_section, encoding="utf-8")
        logger.info(f"[quant] Report → {report_path.name} ({len(charts)} charts)")
        return report_path

    def write_consolidated_report(self) -> Path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{self.role}_consolidated.md"
        report_path = self.reports_dir / filename

        chart_section = ""
        if self._all_charts:
            chart_section = "\n\n## All Charts\n\n" + "\n".join(
                f"![{Path(c).stem}]({c})" for c in self._all_charts
            )

        header = (
            f"# Quantitative Research — Consolidated ({len(self._all_findings)} turns)\n\n"
            f"| Field | Value |\n|---|---|\n"
            f"| Agent | Quant Builder (Claude {self.model}) |\n"
            f"| Date | {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n"
            f"| Total Charts | {len(self._all_charts)} |\n\n---\n\n"
        )
        body = "\n\n---\n\n".join(
            f"## Turn {i + 1}\n\n{f}" for i, f in enumerate(self._all_findings)
        )
        report_path.write_text(header + body + chart_section, encoding="utf-8")
        logger.info(f"[quant] Consolidated report → {report_path.name}")
        return report_path

    def run(self, dry_run: bool = False) -> dict:
        """Run a single research turn — used by CLI."""
        if dry_run:
            return {"status": "dry_run"}
        brief_path = config.REPORTS_DIR.parent / "BRIEF.md"
        if not brief_path.exists():
            brief_path = config.ROOT_DIR / "BRIEF.md"
        brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else "Analyse key market data and produce annotated charts."
        report = self.run_turn(brief)
        return {"status": "ok", "report": str(report)}

    def run_with_recovery(self, dry_run: bool = False) -> dict:
        """Compatibility shim — calls run()."""
        return self.run(dry_run=dry_run)
