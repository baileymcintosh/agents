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

        depth_instruction = (
            "You are the builder agent. Execute the assigned research section with maximum depth. "
            "Use web search extensively — run multiple targeted queries to find the most current information. "
            "Produce specific, evidence-backed analysis with named sources, dates, and figures.\n\n"
            "REQUIRED: At the end of your report, embed a ```chart_data JSON block with any applicable data:\n"
            "- 'scenarios': list of {name, probability, color} for scenario charts\n"
            "- 'market_impacts': list of {name, low, high, direction} for market impact ranges\n"
            "- 'timeline': list of {date, label, severity} for event timelines\n"
            "- Include optional title keys: 'scenario_title', 'market_title', 'timeline_title'\n\n"
            "Example:\n"
            "```chart_data\n"
            '{"scenarios": [{"name": "Containment", "probability": 40, "color": "#27ae60"}], '
            '"scenario_title": "Iran-Israel Scenario Probabilities"}\n'
            "```\n\n"
        ) if not config.FAST_MODE else (
            "You are the builder agent. Produce a concise, direct research brief. "
            "Use web search for the most current facts. Be specific with dates and numbers.\n\n"
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
