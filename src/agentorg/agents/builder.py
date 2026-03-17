"""Builder agent — executes tasks from the planner and produces outputs."""

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
        self.model = config.BUILDER_MODEL

    def _load_latest_plan(self) -> str:
        """Read the most recent planner report to understand current tasks."""
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
        plan = self._load_latest_plan()

        prompt = (
            "You are the builder agent. Below is the current research plan. "
            "Execute the highest-priority task. Show your work step by step. "
            "Produce a detailed output report including: what you did, what you found, "
            "any code or data produced, and next steps.\n\n"
            f"## Current Plan\n\n{plan}"
        )

        if dry_run:
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Build Output", report_content)
        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    BuilderAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
