"""Planner agent — identifies research tasks and produces a prioritized plan."""

from __future__ import annotations

from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent


class PlannerAgent(BaseAgent):
    role = "planner"

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[planner] Starting planning cycle.")

        prompt = (
            "Survey the current state of our research organization. "
            "Identify the top 5 most valuable tasks we should work on this week. "
            "For each task, provide: title, rationale, expected output, and priority (1–5). "
            "Format your response as a structured Markdown report."
        )

        if dry_run:
            logger.info("[planner] Dry-run: skipping Claude call.")
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Weekly Research Plan", report_content)
        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    PlannerAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
