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

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config
from agentorg.evidence import extract_json_block
from agentorg.messaging import AgentMessenger
from agentorg.tools.python_exec import PYTHON_EXEC_TOOL_DEFINITION, PythonExecutor
from agentorg.tools.search import SEARCH_TOOL_DEFINITION, web_search, format_search_results

try:
    import anthropic
except ImportError:  # pragma: no cover - exercised in minimal test envs
    anthropic = None  # type: ignore[assignment]


class QuantBuilderAgent:
    """Claude-based quantitative research agent with Python execution capability."""

    role = "quant_builder"

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY) if anthropic else None
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
        if self.client is None or anthropic is None:
            raise RuntimeError("anthropic package is required for quant_builder.")

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
                except Exception as e:
                    if anthropic is None or not isinstance(e, anthropic.RateLimitError):
                        raise
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
        agenda_items: list[dict[str, str]],
        partner_evidence_brief: str = "",
        clock_context: str = "",
    ) -> dict[str, Any]:
        """Execute one research turn and return prose, charts, and structured evidence."""

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

        if partner_evidence_brief:
            prompt_parts.append(
                f"{partner_evidence_brief}\n\n"
                "Use this shared evidence to avoid duplicate work and test whether your partner's claims show up in the data."
            )

        prompt_parts.append(
            "\n## Instructions\n"
            "1. Fetch live data with yfinance and/or FRED. Use real tickers: "
            "BZ=F (Brent crude), CL=F (WTI), GC=F (Gold), ^GSPC (S&P 500), ^VIX, "
            "TLT (20yr Treasuries). For FRED: 'DCOILBRENTEU', 'CPIAUCSL', 'DGS10'.\n"
            "2. Generate professional publication-quality charts with:\n"
            "   - Concise title (max 10 words, title case)\n"
            "   - Labelled axes with units (e.g. 'Price (USD/bbl)', 'Index Value')\n"
            "   - Annotated vertical lines for key events: use ax.axvline() + ax.text() with fontsize=8, rotation=90, va='bottom'\n"
            "   - Keep annotation labels short (max 4 words) — avoid overlapping text\n"
            "   - Date range covering the conflict period plus 3-month pre-war baseline\n"
            "   - Add a text box (ax.text) in the top-left corner with the single most important statistic\n"
            "3. Run historical comparisons: overlay 1990 Gulf War, 2003 Iraq, 2021 Suez blockage "
            "   on the same chart where relevant.\n"
            "4. Print key statistics to stdout (% change, peak, correlations).\n"
            "5. Call plt.show() after each figure to save it.\n"
            "6. End your response with a `## Questions for Qual` section for anything you see "
            "   in the data that needs a narrative explanation.\n"
            "   Format: 'I see [metric] moved [X%] on [date]. What happened?'\n"
            "7. After your prose, append a machine-readable ```evidence_json block.\n"
        )

        if agenda_items:
            prompt_parts.append(
                "## Assigned Agenda Items\n" +
                "\n".join(f"- {item['id']}: {item['question']}" for item in agenda_items)
            )

        prompt_parts.append(
            "\n## evidence_json schema\n"
            "Return valid JSON with this exact top-level shape after your prose:\n"
            "```evidence_json\n"
            "{\n"
            '  "sources": [\n'
            '    {"id": "S1", "title": "...", "url": "...", "publisher": "...", '
            '"published_at": "YYYY-MM-DD or empty", "tier": "dataset|tier1_primary|tier2_journalism|tier3_analysis|tier4_expert|tier5_unverified", '
            '"summary": "one sentence", "source_type": "dataset|web"}\n'
            "  ],\n"
            '  "claims": [\n'
            '    {"statement": "...", "confidence": 0.0, "materiality": "core|supporting", '
            '"kind": "market_impact|data_point|comparison|risk", "source_ids": ["S1"]}\n'
            "  ],\n"
            '  "addressed_agenda_ids": ["A_xxxx"],\n'
            '  "new_agenda_items": [\n'
            '    {"question": "...", "owner": "qual|quant|shared", "priority": "high|medium|low", "note": "..."}\n'
            "  ]\n"
            "}\n"
            "```\n"
            "Rules:\n"
            "- Include dataset sources for every quantitative claim you rely on.\n"
            "- Every chart-supported or numeric statement in prose must appear in claims.\n"
            "- Use `source_type: dataset` for yfinance/FRED/EIA style inputs.\n"
            "- `addressed_agenda_ids` must only include agenda items you materially advanced.\n"
        )

        prompt = "\n\n".join(prompt_parts)
        findings, charts = self.call_claude(prompt)
        clean_findings, payload = extract_json_block(findings)
        self._all_findings.append(clean_findings)
        self._all_charts.extend(charts)

        # Write charts manifest so reporter can embed + explain every chart
        self._write_charts_manifest(charts, clean_findings)

        # Extract and post questions for qual
        self._extract_and_post_messages(clean_findings, messenger)

        return {"content": clean_findings, "payload": payload, "charts": charts}

    def _write_charts_manifest(self, charts: list[str], findings: str) -> None:
        """Write a JSON manifest mapping chart filenames to descriptions extracted from findings."""
        import json, re
        manifest_path = self.reports_dir / "charts_manifest.json"

        # Load existing manifest if present
        existing: list[dict] = []
        if manifest_path.exists():
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        # Extract chart descriptions from findings text
        # Look for patterns like "Chart N:" or "Figure N:" followed by description
        chart_descs: list[str] = []
        for match in re.finditer(
            r"(?:chart|figure|plot)\s*\d*\s*[:\-–]\s*([^\n]{10,150})",
            findings, re.IGNORECASE
        ):
            chart_descs.append(match.group(1).strip())

        for i, chart_path in enumerate(charts):
            fname = Path(chart_path).name
            # Skip if already in manifest
            if any(e["filename"] == fname for e in existing):
                continue
            desc = chart_descs[i] if i < len(chart_descs) else f"Quantitative chart {i + 1}"
            existing.append({
                "filename": fname,
                "title": desc[:80],
                "description": desc,
            })

        manifest_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
        logger.info(f"[quant] Charts manifest → {len(existing)} charts recorded")

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
        messenger = AgentMessenger(run_id="standalone")
        result = self.run_turn(turn=1, research_plan=brief, messenger=messenger, agenda_items=[])
        report_path = self.write_report(turn=1, content=result["content"], charts=result["charts"])
        return {"status": "ok", "report": str(report_path)}

    def run_with_recovery(self, dry_run: bool = False) -> dict:
        """Compatibility shim — calls run()."""
        return self.run(dry_run=dry_run)
