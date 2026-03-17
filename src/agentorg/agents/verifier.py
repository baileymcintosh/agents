"""Verifier agent — reviews builder outputs and writes a QA sign-off report."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config


class VerifierAgent(BaseAgent):
    role = "verifier"

    def __init__(self) -> None:
        super().__init__()
        self.model = config.VERIFIER_MODEL

    def _load_latest_build(self) -> str:
        builds = sorted(
            config.REPORTS_DIR.glob("*_builder_*.md"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not builds:
            return "No builder report found. Please run the builder first."
        latest: Path = builds[0]
        logger.info(f"[verifier] Reviewing: {latest.name}")
        return latest.read_text(encoding="utf-8")

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[verifier] Starting verification cycle.")
        self.post_slack_progress("🔎", "starting", "Reviewing research output for accuracy, depth, and quality...")

        build_output = self._load_latest_build()

        prompt = (
            "You are the verifier agent. Critically review the research output below. "
            "Issue a verdict (PASS / NEEDS REVISION / FAIL), a confidence score (0–100), "
            "and specific numbered findings on what is strong and what needs work.\n\n"
            f"## Research Output\n\n{build_output}"
        )

        if dry_run:
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Verification Report", report_content)

        if not dry_run:
            brief = self.generate_slack_brief(report_content)
        else:
            brief = "Dry-run complete."
        self.post_slack_progress("✅", "done", brief)

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    VerifierAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
