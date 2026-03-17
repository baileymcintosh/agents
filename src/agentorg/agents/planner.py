"""Planner agent — identifies research tasks and produces a prioritized plan."""

from __future__ import annotations

from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config


class PlannerAgent(BaseAgent):
    role = "planner"

    def __init__(self) -> None:
        super().__init__()
        self.model = config.PLANNER_MODEL

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[planner] Starting planning cycle.")
        self.post_slack_progress("🔍", "starting", "Reading PROJECT.md and scanning the research landscape...")

        project_brief = ""
        project_path = config.ROOT_DIR / "PROJECT.md"
        if project_path.exists():
            project_brief = f"## Active Project Brief\n\n{project_path.read_text(encoding='utf-8')}"

        prompt = (
            "Read the active project brief below carefully. "
            "Survey what research has already been completed by reading any prior reports mentioned. "
            "Then produce a detailed research plan for this cycle: identify the highest-priority section "
            "to work on, write a precise brief for the Builder, and track overall project progress.\n\n"
            f"{project_brief}"
        )

        if dry_run:
            logger.info("[planner] Dry-run: skipping Claude call.")
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Research Plan", report_content)

        # Extract a one-line summary for the Slack update
        first_line = next(
            (line.strip() for line in report_content.split("\n") if line.strip() and not line.startswith("#")),
            "Plan complete."
        )[:200]
        self.post_slack_progress("✅", "done", f"Research plan ready. {first_line}")

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    PlannerAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
