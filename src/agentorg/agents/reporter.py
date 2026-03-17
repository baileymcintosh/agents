"""Reporter agent — synthesizes research into a Jupyter notebook with inline charts."""

from __future__ import annotations

import datetime
import json
from pathlib import Path
from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config


class ReporterAgent(BaseAgent):
    role = "reporter"

    def __init__(self) -> None:
        super().__init__()
        if not config.FAST_MODE:
            self.model = config.REPORTER_MODEL
        self.max_tokens = config.AGENT_MAX_TOKENS
        self.clock = None  # never cap reporter tokens

    def _gather_recent_reports(self) -> str:
        sections = []
        builder_files = sorted(
            config.REPORTS_DIR.glob("*_builder_*.md"),
            key=lambda f: f.stat().st_mtime,
        )
        for f in builder_files:
            content = f.read_text(encoding="utf-8")
            if "_Dry-run mode_" in content or "Dry-run mode" in content:
                continue
            sections.append(f"## Builder Report — {f.stem}\n\n{content}")

        for agent_role in ("planner", "verifier"):
            files = sorted(
                config.REPORTS_DIR.glob(f"*_{agent_role}_*.md"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if files:
                content = files[0].read_text(encoding="utf-8")
                if "_Dry-run mode_" in content or "Dry-run mode" in content:
                    continue
                sections.append(f"## {agent_role.capitalize()} Report\n\n{content}")

        return "\n\n---\n\n".join(sections) if sections else "No reports found."

    def _extract_chart_data(self, summary: str, context: str) -> dict[str, Any]:
        """
        Ask Claude directly for structured chart data based on the full research.
        Much more reliable than hoping the builder embedded correct JSON.
        """
        prompt = (
            "Based on the research below, output ONLY a JSON object (no explanation, no markdown, "
            "just raw JSON) with the following structure. Use real numbers from the research.\n\n"
            "{\n"
            '  "scenario_title": "string",\n'
            '  "scenarios": [{"name": "string", "probability": number_0_to_100, "color": "#hexcode"}, ...],\n'
            '  "market_title": "string",\n'
            '  "market_impacts": [{"name": "string", "low": number, "high": number, "direction": "up"|"down"}, ...],\n'
            '  "timeline_title": "string",\n'
            '  "timeline": [{"date": "string", "label": "string", "severity": "high"|"medium"|"low"}, ...]\n'
            "}\n\n"
            "Rules:\n"
            "- scenarios: 4-6 items, probabilities must sum to ~100\n"
            "- market_impacts: 6-10 assets with realistic % ranges (can be negative)\n"
            "- timeline: 6-10 key events in chronological order\n"
            "- colors: use #27ae60 (green/positive), #e74c3c (red/high-risk), "
            "#f39c12 (yellow/uncertain), #3498db (blue/neutral), #8e44ad (purple/severe)\n\n"
            f"Research summary:\n{summary[:4000]}\n\nFull context:\n{context[:3000]}"
        )
        try:
            raw = self.call_claude(prompt)
            # Strip any accidental markdown fences
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw.strip())
        except Exception as e:
            logger.warning(f"[reporter] Chart data extraction failed: {e}")
            return {}

    def _generate_charts(self, data: dict[str, Any]) -> dict[str, Path]:
        from agentorg.reporting.charts import (
            scenario_probability_chart,
            market_impact_chart,
            timeline_chart,
        )
        paths: dict[str, Path] = {}

        if "scenarios" in data:
            p = scenario_probability_chart(
                data["scenarios"][:10],
                config.REPORTS_DIR / "chart_scenarios.png",
                title=data.get("scenario_title", "Scenario Probability Distribution"),
            )
            if p:
                paths["scenarios"] = p

        if "market_impacts" in data:
            p = market_impact_chart(
                data["market_impacts"][:12],
                config.REPORTS_DIR / "chart_market_impact.png",
                title=data.get("market_title", "Estimated Market Impact by Asset Class"),
            )
            if p:
                paths["market_impacts"] = p

        if "timeline" in data:
            p = timeline_chart(
                data["timeline"][:14],
                config.REPORTS_DIR / "chart_timeline.png",
                title=data.get("timeline_title", "Event Timeline"),
            )
            if p:
                paths["timeline"] = p

        logger.info(f"[reporter] Generated {len(paths)} chart(s): {list(paths.keys())}")
        return paths

    def _build_notebook(
        self, summary: str, chart_paths: dict[str, Path], report_path: Path
    ) -> Path | None:
        try:
            from agentorg.reporting.notebook import build_notebook, save_notebook
            meta = {
                "project": "Iran–USA–Israel War: Strategic Assessment",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "model": self.model,
            }
            nb = build_notebook(summary, chart_paths, metadata=meta)
            if nb is None:
                return None
            nb_path = report_path.with_suffix(".ipynb")
            save_notebook(nb, nb_path)
            logger.info(f"[reporter] Notebook → {nb_path.name}")
            return nb_path
        except Exception as e:
            logger.warning(f"[reporter] Notebook build failed: {e}")
            return None

    def _export_pdf(self, report_path: Path) -> Path | None:
        import subprocess
        pdf_path = report_path.with_suffix(".pdf")
        cmd = [
            "pandoc", str(report_path),
            "--output", str(pdf_path),
            "--pdf-engine=xelatex",
            "--toc",
            f"--resource-path={config.REPORTS_DIR}",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=11pt",
            "-V", "colorlinks=true",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                logger.info(f"[reporter] PDF → {pdf_path.name}")
                return pdf_path
            logger.warning(f"[reporter] pandoc failed: {result.stderr[:300]}")
        except Exception as e:
            logger.warning(f"[reporter] PDF export failed: {e}")
        return None

    def _post_slack(self, brief: str, nb_path: Path | None, pdf_path: Path | None, report_path: Path) -> None:
        if not config.SLACK_BOT_TOKEN or not config.SLACK_EXECUTIVE_CHANNEL_ID:
            return
        try:
            from agentorg.slack_bot.client import SlackClient
            slack = SlackClient()
            cycle_date = report_path.stem.split("_")[0]
            slack.post_message(
                channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                text=f"*Research Report — {cycle_date}*\n\n{brief}",
            )
            for path, title, comment in [
                (nb_path, f"Report — {cycle_date} (Notebook)", "Open in VS Code or Jupyter — charts inline."),
                (pdf_path, f"Report — {cycle_date} (PDF)", "PDF version."),
            ]:
                if path:
                    try:
                        slack.upload_file(
                            channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                            file_path=str(path), title=title, initial_comment=comment,
                        )
                    except Exception as e:
                        logger.warning(f"[reporter] Slack upload failed: {e}")
        except Exception as e:
            logger.warning(f"[reporter] Slack post failed (non-fatal): {e}")

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[reporter] Starting.")
        self.post_slack_progress("📝", "starting", "Synthesizing all research into final report...")

        context = self._gather_recent_reports()

        summary_prompt = (
            "You are the reporter agent. Based on ALL builder reports below (multiple research cycles), "
            "write a comprehensive, publication-quality executive summary.\n\n"
            "Use these exact section headings:\n"
            "# [Project Title]\n"
            "## One-Line Status\n"
            "## Situation Overview\n"
            "## Key Findings\n"
            "## Scenario Outlook\n"
            "## Financial Markets Implications\n"
            "## Historical Precedents & Lessons\n"
            "## Quality Assessment\n"
            "## Recommended Next Steps\n\n"
            "Be comprehensive — synthesize ALL cycles. Use specific facts, dates, figures, named sources. "
            "This is the final deliverable for senior leadership.\n\n"
            f"{context}"
        )

        if dry_run:
            summary = "_Dry-run mode._"
            brief = "_Dry-run mode._"
        else:
            summary = self.call_claude(summary_prompt)
            brief_prompt = (
                "Write a 3-sentence Slack update for a senior executive. "
                "What was researched, the single most important finding, one key risk. "
                "Specific, no filler.\n\n" + summary[:3000]
            )
            brief = self.call_claude(brief_prompt)

        # Extract chart data directly from Claude (reliable) rather than parsing builder JSON
        chart_paths: dict[str, Path] = {}
        if not dry_run:
            chart_data = self._extract_chart_data(summary, context)
            if chart_data:
                chart_paths = self._generate_charts(chart_data)

        # Inject chart image refs into markdown for the saved .md and PDF
        md_with_charts = summary
        if chart_paths:
            # Insert images after their relevant headings
            triggers = {
                "timeline": ["## situation", "## one-line", "## overview"],
                "scenarios": ["## scenario"],
                "market_impacts": ["## financial", "## market"],
            }
            lines = summary.split("\n")
            out = []
            for line in lines:
                out.append(line)
                ll = line.lower()
                for key, keywords in triggers.items():
                    if key in chart_paths and any(ll.startswith(kw) for kw in keywords):
                        p = chart_paths[key]
                        out.append(f"\n![{p.stem.replace('_', ' ').title()}]({p})\n")
                        chart_paths.pop(key)  # only insert once
                        break
            # Append any remaining charts at end
            for key, p in chart_paths.items():
                out.append(f"\n---\n\n## {key.replace('_', ' ').title()}\n\n![{p.stem}]({p})\n")
            md_with_charts = "\n".join(out)
            # Rebuild chart_paths (we popped from it above — re-collect from disk)
            chart_paths = {
                p.stem.split("chart_")[1]: p
                for p in config.REPORTS_DIR.glob("chart_*.png")
            }

        report_path = self.write_report("Executive Summary", md_with_charts)

        # Build Jupyter notebook — primary output, open in VS Code
        nb_path = self._build_notebook(summary, chart_paths, report_path) if not dry_run else None

        # PDF
        pdf_path: Path | None = None
        if not dry_run and config.PDF_EXPORT_ENABLED and not config.FAST_MODE:
            pdf_path = self._export_pdf(report_path)

        # Log where outputs are
        logger.info(f"[reporter] Outputs in {config.REPORTS_DIR}:")
        logger.info(f"  Markdown: {report_path.name}")
        if nb_path:
            logger.info(f"  Notebook: {nb_path.name}  ← open this in VS Code")
        if pdf_path:
            logger.info(f"  PDF:      {pdf_path.name}")

        # Slack — secondary, best-effort
        if not dry_run:
            self._post_slack(brief, nb_path, pdf_path, report_path)

        self.post_slack_progress("✅", "done", brief[:200] if not dry_run else "Dry-run complete.")
        return {
            "status": "ok",
            "report": str(report_path),
            "notebook": str(nb_path) if nb_path else None,
            "pdf": str(pdf_path) if pdf_path else None,
        }


def main(dry_run: bool = False) -> None:
    ReporterAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
