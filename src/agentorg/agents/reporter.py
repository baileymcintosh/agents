"""Reporter agent — synthesizes findings into an executive summary, exports to PDF + notebook, posts to Slack."""

from __future__ import annotations

import datetime
import re
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
        # Reporter always gets full token budget — synthesizes everything, must never truncate
        self.max_tokens = config.AGENT_MAX_TOKENS
        self.clock = None  # disable time-budget token cap for reporter

    def _gather_recent_reports(self) -> str:
        """
        Collect all builder reports + latest planner/verifier from this session.
        Builder reports accumulate across cycles — we want ALL of them for synthesis.
        """
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
                sections.append(f"## {agent_role.capitalize()} Report (latest)\n\n{content}")

        return "\n\n---\n\n".join(sections) if sections else "No live reports found this cycle."

    def _write_slack_brief(self, summary: str) -> str:
        brief_prompt = (
            "Condense the following executive summary into a Slack message of exactly 3–4 sentences. "
            "Write for a senior executive who is about to open a detailed report. "
            "Cover: what was researched, the single most important finding, and one key risk or next step. "
            "Be specific and direct. No bullet points — flowing prose only.\n\n"
            f"{summary}"
        )
        return self.call_claude(brief_prompt)

    def _collect_chart_data(self, summary: str) -> dict[str, Any]:
        """Merge chart_data blocks from all builder reports and the summary."""
        from agentorg.reporting.charts import extract_chart_data
        combined: dict[str, Any] = {}
        builder_files = sorted(
            config.REPORTS_DIR.glob("*_builder_*.md"),
            key=lambda f: f.stat().st_mtime,
        )
        for bf in builder_files:
            text = bf.read_text(encoding="utf-8")
            data = extract_chart_data(text)
            for key, val in data.items():
                if key in combined and isinstance(combined[key], list) and isinstance(val, list):
                    combined[key].extend(val)
                else:
                    combined[key] = val
        combined.update(extract_chart_data(summary))
        return combined

    def _generate_charts(self, combined_data: dict[str, Any]) -> dict[str, Path]:
        """Generate PNG charts from combined data. Returns {key: path} dict."""
        from agentorg.reporting.charts import (
            scenario_probability_chart,
            market_impact_chart,
            timeline_chart,
        )
        chart_paths: dict[str, Path] = {}

        if "scenarios" in combined_data:
            p = scenario_probability_chart(
                combined_data["scenarios"][:10],
                config.REPORTS_DIR / "chart_scenarios.png",
                title=combined_data.get("scenario_title", "Scenario Probability Distribution"),
            )
            if p:
                chart_paths["scenarios"] = p

        if "market_impacts" in combined_data:
            p = market_impact_chart(
                combined_data["market_impacts"][:12],
                config.REPORTS_DIR / "chart_market_impact.png",
                title=combined_data.get("market_title", "Estimated Market Impact by Asset Class"),
            )
            if p:
                chart_paths["market_impacts"] = p

        if "timeline" in combined_data:
            p = timeline_chart(
                combined_data["timeline"][:14],
                config.REPORTS_DIR / "chart_timeline.png",
                title=combined_data.get("timeline_title", "Event Timeline"),
            )
            if p:
                chart_paths["timeline"] = p

        logger.info(f"[reporter] Generated {len(chart_paths)} chart(s): {list(chart_paths.keys())}")
        return chart_paths

    def _inject_charts_into_markdown(self, text: str, chart_paths: dict[str, Path]) -> str:
        """
        Insert chart image references inline in the markdown at appropriate sections.
        The timeline goes near the top; scenario/market charts go after their sections.
        Pandoc then embeds these as full-bleed figures in the PDF.
        """
        TRIGGERS = {
            "scenarios": ["scenario", "outlook", "probability"],
            "market_impacts": ["market", "financial", "asset", "energy", "oil"],
            "timeline": ["timeline", "chronol", "situation", "status", "one-line"],
        }

        used: set[str] = set()

        def _img(key: str) -> str:
            path = chart_paths[key]
            label = path.stem.replace("_", " ").title()
            return f"\n\n![{label}]({path})\n\n"

        lines = text.split("\n")
        result = []

        for line in lines:
            result.append(line)
            # After a heading line, check if we should insert a chart
            if line.startswith("#"):
                heading_lower = line.lower()
                for key, keywords in TRIGGERS.items():
                    if key in chart_paths and key not in used:
                        if any(kw in heading_lower for kw in keywords):
                            result.append(_img(key))
                            used.add(key)
                            break

        # Append any unused charts at the end
        for key, path in chart_paths.items():
            if key not in used:
                label = key.replace("_", " ").title()
                result.append(f"\n\n---\n\n## {label}\n\n")
                result.append(_img(key))

        return "\n".join(result)

    def _export_pdf(self, md_path: Path, chart_paths: dict[str, Path]) -> Path | None:
        """Generate PDF from chart-enriched markdown via pandoc."""
        import subprocess
        pdf_path = md_path.with_suffix(".pdf")
        # Resource path includes the reports dir so pandoc finds the PNG files
        cmd = [
            "pandoc", str(md_path),
            "--output", str(pdf_path),
            "--pdf-engine=xelatex",
            "--toc",
            f"--resource-path={config.REPORTS_DIR}",
            "-V", "geometry:margin=1in",
            "-V", "fontsize=11pt",
            "-V", "colorlinks=true",
            "--highlight-style=tango",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                logger.info(f"[reporter] PDF ready: {pdf_path.name}")
                return pdf_path
            logger.warning(f"[reporter] pandoc failed: {result.stderr[:500]}")
        except Exception as e:
            logger.warning(f"[reporter] PDF export failed: {e}")
        return None

    def _export_notebook(
        self, summary: str, chart_paths: dict[str, Path], report_path: Path
    ) -> Path | None:
        """Build and save a Jupyter notebook with charts embedded as outputs."""
        try:
            from agentorg.reporting.notebook import build_notebook, save_notebook
            meta = {
                "project": "Iran–USA–Israel War Research",
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                "model": self.model,
            }
            nb = build_notebook(summary, chart_paths, metadata=meta)
            if nb is None:
                return None
            nb_path = report_path.with_suffix(".ipynb")
            return save_notebook(nb, nb_path)
        except Exception as e:
            logger.warning(f"[reporter] Notebook export failed (non-fatal): {e}")
            return None

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[reporter] Building executive summary.")
        self.post_slack_progress("📝", "starting", "Synthesizing all research cycles into final report...")

        context = self._gather_recent_reports()

        summary_prompt = (
            "You are the reporter agent for a professional research organization. "
            "Based on ALL the builder reports below (covering multiple research cycles), "
            "write a comprehensive, publication-quality executive summary.\n\n"
            "Structure:\n"
            "# [Project Title]\n\n"
            "## One-Line Status\n"
            "## Situation Overview\n"
            "## Key Findings\n"
            "## Scenario Outlook\n"
            "## Financial Markets Implications\n"
            "## Historical Precedents\n"
            "## Quality Assessment\n"
            "## Recommended Next Steps\n\n"
            "Be comprehensive — synthesize ALL cycles, not just the latest. "
            "Use specific facts, dates, figures, and named sources. "
            "This is the final deliverable that goes to senior leadership.\n\n"
            f"{context}"
        )

        if dry_run:
            summary = "_Dry-run mode — no Claude call made._"
            brief = "_Dry-run mode._"
        else:
            summary = self.call_claude(summary_prompt)
            brief = self._write_slack_brief(summary)

        # Collect chart data and generate PNGs
        chart_paths: dict[str, Path] = {}
        if not dry_run:
            try:
                combined_data = self._collect_chart_data(summary)
                chart_paths = self._generate_charts(combined_data)
            except Exception as e:
                logger.warning(f"[reporter] Chart generation failed (non-fatal): {e}")

        # Build chart-enriched markdown for PDF
        enriched_md = self._inject_charts_into_markdown(summary, chart_paths) if chart_paths else summary
        report_path = self.write_report("Executive Summary", enriched_md)

        # Export notebook (primary deliverable — charts inline, code hidden)
        nb_path: Path | None = None
        if not dry_run and chart_paths:
            nb_path = self._export_notebook(summary, chart_paths, report_path)

        # Export PDF from chart-enriched markdown
        pdf_path: Path | None = None
        if not dry_run and config.PDF_EXPORT_ENABLED and not config.FAST_MODE:
            pdf_path = self._export_pdf(report_path, chart_paths)

        # Post to Slack
        if config.SLACK_BOT_TOKEN and config.SLACK_EXECUTIVE_CHANNEL_ID and not dry_run:
            try:
                from agentorg.slack_bot.client import SlackClient
                slack = SlackClient()

                cycle_date = report_path.stem.split("_")[0]
                slack.post_message(
                    channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                    text=f"*Research Report — {cycle_date}*\n\n{brief}",
                )

                # Upload notebook first (best format — charts inline, self-contained)
                if nb_path:
                    slack.upload_file(
                        channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                        file_path=str(nb_path),
                        title=f"Research Report — {cycle_date} (Notebook)",
                        initial_comment="Full report with inline charts attached (open in Jupyter or VS Code).",
                    )

                # Upload PDF if available
                if pdf_path:
                    slack.upload_file(
                        channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                        file_path=str(pdf_path),
                        title=f"Research Report — {cycle_date} (PDF)",
                        initial_comment="PDF version attached." if nb_path else "Full report attached.",
                    )
                elif not nb_path:
                    # Fallback to markdown if neither notebook nor PDF
                    slack.upload_file(
                        channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                        file_path=str(report_path),
                        title=f"Executive Summary — {cycle_date}",
                        initial_comment="Full report attached.",
                    )

                logger.info("[reporter] Slack delivery complete.")
            except Exception as e:
                logger.error(f"[reporter] Slack error (non-fatal): {e}")

        self.post_slack_progress("✅", "done", brief)
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
