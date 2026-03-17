"""Builder agent — executes research tasks from the planner and produces outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config


class BuilderAgent(BaseAgent):
    role = "builder"

    def __init__(self) -> None:
        super().__init__()
        if not config.FAST_MODE:
            self.model = config.BUILDER_MODEL

    def _load_latest_plan(self) -> str:
        plans = sorted(
            config.REPORTS_DIR.glob("*_planner_*.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not plans:
            return "No planner report found. Please run the planner first."
        latest: Path = plans[0]
        logger.info(f"[builder] Using plan: {latest.name}")
        return latest.read_text(encoding="utf-8")

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[builder] Starting build cycle.")
        self.post_slack_progress("⚙️", "starting", "Reading research plan and beginning deep analysis with web search...")

        plan = self._load_latest_plan()

        project_brief = ""
        project_path = config.ROOT_DIR / "PROJECT.md"
        if project_path.exists():
            project_brief = project_path.read_text(encoding="utf-8")

        chart_data_instruction = (
            "\n\n════════════════════════════════════════\n"
            "MANDATORY: END YOUR REPORT WITH A chart_data BLOCK\n"
            "════════════════════════════════════════\n"
            "You MUST include a ```chart_data block at the very end of your report.\n"
            "This is not optional. The system will not generate graphs without it.\n"
            "Populate every field that is relevant to your section.\n\n"
            "```chart_data\n"
            "{\n"
            '  "scenario_title": "Iran War: Scenario Probabilities",\n'
            '  "scenarios": [\n'
            '    {"name": "Negotiated ceasefire", "probability": 25, "color": "#27ae60"},\n'
            '    {"name": "Continued air campaign", "probability": 40, "color": "#f39c12"},\n'
            '    {"name": "Iranian nuclear breakout", "probability": 15, "color": "#e74c3c"},\n'
            '    {"name": "Full regional war", "probability": 20, "color": "#8e44ad"}\n'
            "  ],\n"
            '  "market_title": "Estimated Market Impact",\n'
            '  "market_impacts": [\n'
            '    {"name": "Brent Crude", "low": 15, "high": 60, "direction": "up"},\n'
            '    {"name": "S&P 500", "low": -15, "high": -5, "direction": "down"},\n'
            '    {"name": "Gold", "low": 5, "high": 20, "direction": "up"}\n'
            "  ],\n"
            '  "timeline_title": "Key Conflict Events",\n'
            '  "timeline": [\n'
            '    {"date": "Feb 28 2026", "label": "Operation Epic Fury launched", "severity": "high"},\n'
            '    {"date": "Mar 2 2026", "label": "Hormuz closed", "severity": "high"},\n'
            '    {"date": "Mar 8 2026", "label": "New Supreme Leader named", "severity": "medium"}\n'
            "  ]\n"
            "}\n"
            "```\n"
            "Replace the example values above with YOUR ACTUAL RESEARCH DATA.\n"
            "Use real probability estimates, real price ranges, real dates and events.\n"
            "════════════════════════════════════════\n\n"
        )

        depth_instruction = (
            "You are the builder agent. Execute the assigned research section with maximum depth. "
            "Use web search extensively — run multiple targeted queries to find the most current information. "
            "Produce specific, evidence-backed analysis with named sources, dates, and figures."
            + chart_data_instruction
        ) if not config.FAST_MODE else (
            "You are the builder agent. Produce a concise, direct research brief. "
            "Use web search for the most current facts. Be specific with dates and numbers."
            + chart_data_instruction
        )

        prompt = (
            f"{depth_instruction}"
            f"## Project Brief\n\n{project_brief}\n\n"
            f"## Research Plan\n\n{plan}"
        )

        if dry_run:
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Research Section", report_content)

        if not dry_run:
            brief = self.generate_slack_brief(report_content)
        else:
            brief = "Dry-run complete."
        self.post_slack_progress("✅", "done", brief)

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    BuilderAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
