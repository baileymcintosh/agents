"""Reporter agent — synthesizes findings into an executive summary, exports to PDF, posts to Slack."""

from __future__ import annotations

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
        # Reporter always gets full token budget — it synthesizes everything and must never truncate
        self.max_tokens = config.AGENT_MAX_TOKENS
        self.clock = None  # disable time-budget token cap for reporter

    def _gather_recent_reports(self) -> str:
        """
        Collect all builder reports + latest planner/verifier from this session.
        Builder reports accumulate across cycles — we want ALL of them for synthesis.
        """
        sections = []

        # All builder reports (every cycle adds a new section — include them all)
        builder_files = sorted(
            config.REPORTS_DIR.glob("*_builder_*.md"),
            key=lambda f: f.stat().st_mtime,
        )
        for f in builder_files:
            content = f.read_text(encoding="utf-8")
            if "_Dry-run mode_" in content or "Dry-run mode" in content:
                continue
            sections.append(f"## Builder Report — {f.stem}\n\n{content}")

        # Latest planner and verifier only (for context on project status and QA verdict)
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
        """
        Ask Claude to condense the executive summary into a 3–4 sentence Slack brief.
        This is what gets posted as the Slack message — the full PDF is attached separately.
        """
        brief_prompt = (
            "Condense the following executive summary into a Slack message of exactly 3–4 sentences. "
            "Write for a senior executive who is about to open a detailed PDF report. "
            "Cover: what was researched, the single most important finding, and one key risk or next step. "
            "Be specific and direct. No bullet points — flowing prose only.\n\n"
            f"{summary}"
        )
        return self.call_claude(brief_prompt)

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[reporter] Building executive summary.")
        context = self._gather_recent_reports()

        summary_prompt = (
            "You are the reporter agent for a professional research organization. "
            "Based on the reports below, write a comprehensive executive summary. "
            "Structure it as a formal research brief with these sections:\n"
            "1. **One-Line Status** — single sentence on where things stand\n"
            "2. **What Was Researched This Cycle** — what the team worked on\n"
            "3. **Key Findings** — the most important discoveries, specific and direct\n"
            "4. **Scenario Outlook** — if scenarios were developed, summarize the top 2-3\n"
            "5. **Financial Markets Implications** — if relevant, key market signals\n"
            "6. **Quality Assessment** — verifier's verdict and confidence\n"
            "7. **Recommended Next Steps** — what should happen next cycle\n\n"
            "Write clearly. No jargon. This goes to a non-technical executive "
            "who will read the full PDF for detail.\n\n"
            f"{context}"
        )

        if dry_run:
            summary = "_Dry-run mode — no Claude call made._"
            brief = "_Dry-run mode._"
        else:
            summary = self.call_claude(summary_prompt)
            brief = self._write_slack_brief(summary)

        # Write the full Markdown report
        report_path = self.write_report("Executive Summary", summary)

        # Generate charts — scan ALL builder reports for chart_data blocks, not just the summary
        chart_paths: list[Path] = []
        if not dry_run:
            try:
                from agentorg.reporting.charts import generate_all_charts, extract_chart_data
                # Collect chart_data from every builder report in the session
                combined_data: dict = {}
                builder_files = sorted(config.REPORTS_DIR.glob("*_builder_*.md"), key=lambda f: f.stat().st_mtime)
                for bf in builder_files:
                    text = bf.read_text(encoding="utf-8")
                    data = extract_chart_data(text)
                    # Merge: later cycles append to lists, don't overwrite
                    for key, val in data.items():
                        if key in combined_data and isinstance(combined_data[key], list) and isinstance(val, list):
                            combined_data[key].extend(val)
                        else:
                            combined_data[key] = val
                # Also scan the summary itself
                combined_data.update(extract_chart_data(summary))

                # Generate whichever chart types we have data for
                from agentorg.reporting.charts import scenario_probability_chart, market_impact_chart, timeline_chart
                if "scenarios" in combined_data:
                    p = scenario_probability_chart(
                        combined_data["scenarios"][:10],  # cap at 10 bars
                        config.REPORTS_DIR / "chart_scenarios.png",
                        title=combined_data.get("scenario_title", "Scenario Probability Distribution"),
                    )
                    if p: chart_paths.append(p)
                if "market_impacts" in combined_data:
                    p = market_impact_chart(
                        combined_data["market_impacts"][:12],
                        config.REPORTS_DIR / "chart_market_impact.png",
                        title=combined_data.get("market_title", "Estimated Market Impact by Asset Class"),
                    )
                    if p: chart_paths.append(p)
                if "timeline" in combined_data:
                    p = timeline_chart(
                        combined_data["timeline"][:12],
                        config.REPORTS_DIR / "chart_timeline.png",
                        title=combined_data.get("timeline_title", "Event Timeline"),
                    )
                    if p: chart_paths.append(p)
                logger.info(f"[reporter] Generated {len(chart_paths)} chart(s)")
            except Exception as e:
                logger.warning(f"[reporter] Chart generation failed (non-fatal): {e}")

        # Export to LaTeX PDF (skip in fast mode)
        pdf_path: Path | None = None
        if not dry_run and config.PDF_EXPORT_ENABLED and not config.FAST_MODE:
            try:
                from agentorg.reporting.generator import ReportGenerator
                gen = ReportGenerator()
                pdf_path = gen.export_to_pdf(report_path)
                if pdf_path:
                    logger.info(f"[reporter] PDF ready: {pdf_path.name}")
            except Exception as e:
                logger.warning(f"[reporter] PDF export failed (non-fatal): {e}")

        # Post to Slack — brief message + charts + PDF attachment
        if config.SLACK_BOT_TOKEN and config.SLACK_EXECUTIVE_CHANNEL_ID and not dry_run:
            try:
                from agentorg.slack_bot.client import SlackClient
                slack = SlackClient()

                cycle_date = report_path.stem.split("_")[0]  # YYYYMMDD
                slack.post_message(
                    channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                    text=f"*Research Report — {cycle_date}*\n\n{brief}",
                )

                # Upload any generated charts
                for i, chart_path in enumerate(chart_paths):
                    try:
                        slack.upload_file(
                            channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                            file_path=str(chart_path),
                            title=chart_path.stem.replace("_", " ").title(),
                            initial_comment="" if i > 0 else "Charts from this cycle:",
                        )
                    except Exception as e:
                        logger.warning(f"[reporter] Chart upload failed (non-fatal): {e}")

                # Upload the PDF (preferred) or fall back to Markdown
                file_to_upload = str(pdf_path) if pdf_path else str(report_path)
                file_title = f"Executive Summary — {cycle_date}"
                slack.upload_file(
                    channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                    file_path=file_to_upload,
                    title=file_title,
                    initial_comment="Full report attached.",
                )
                logger.info("[reporter] Slack post + charts + file upload complete.")
            except Exception as e:
                logger.error(f"[reporter] Slack error (non-fatal): {e}")

        return {"status": "ok", "report": str(report_path), "pdf": str(pdf_path) if pdf_path else None}


def main(dry_run: bool = False) -> None:
    ReporterAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
