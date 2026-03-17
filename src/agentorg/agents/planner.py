"""Planner agent — identifies research tasks and produces a prioritized plan."""

from __future__ import annotations

from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config
from agentorg.timing import RunClock, parse_budget_string


class PlannerAgent(BaseAgent):
    role = "planner"

    def __init__(self) -> None:
        super().__init__()
        if not config.FAST_MODE:
            self.model = config.PLANNER_MODEL

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[planner] Starting planning cycle.")

        # Planner always initializes the clock — it runs first in every pipeline
        if config.TIME_BUDGET and not self.clock:
            budget_minutes = parse_budget_string(config.TIME_BUDGET)
            self.clock = RunClock.initialize(budget_minutes)
            logger.info(f"[planner] Time budget: {budget_minutes:.0f} min")

        self.post_slack_progress("🔍", "starting", "Reading the project brief and scanning for current intelligence...")

        project_brief = ""
        project_path = config.ROOT_DIR / "PROJECT.md"
        if project_path.exists():
            project_brief = f"## Active Project Brief\n\n{project_path.read_text(encoding='utf-8')}"

        time_allocation = self.clock.planner_context() if self.clock else ""

        prompt = (
            "Read the active project brief below carefully. "
            "Survey what research has already been completed by checking prior reports. "
            "Produce a detailed research plan for this cycle: identify the highest-priority section "
            "to work on next, write a precise brief for the Builder, and track overall project progress.\n\n"
            f"{time_allocation}"
            f"{project_brief}"
        )

        if dry_run:
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Research Plan", report_content)

        if not dry_run:
            brief = self.generate_slack_brief(report_content)
        else:
            brief = "Dry-run complete."
        self.post_slack_progress("✅", "done", brief)

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    PlannerAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
