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
        self.post_slack_progress("⚙️", "starting", "Reading the research plan and beginning deep analysis...")

        plan = self._load_latest_plan()

        project_brief = ""
        project_path = config.ROOT_DIR / "PROJECT.md"
        if project_path.exists():
            project_brief = project_path.read_text(encoding="utf-8")

        prompt = (
            "You are the builder agent. Below is the research plan for this cycle and the project brief. "
            "Execute the assigned research section with maximum depth and rigor. "
            "Search the web extensively for current information — use multiple targeted queries. "
            "Produce a detailed, specific research section with evidence, citations, and analysis.\n\n"
            f"## Project Brief\n\n{project_brief}\n\n"
            f"## Research Plan\n\n{plan}"
        )

        if dry_run:
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Research Section", report_content)

        first_line = next(
            (line.strip() for line in report_content.split("\n") if line.strip() and not line.startswith("#")),
            "Research section complete."
        )[:200]
        self.post_slack_progress("✅", "done", f"Section complete. {first_line}")

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    BuilderAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
