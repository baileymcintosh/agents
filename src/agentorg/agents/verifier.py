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
        self.post_slack_progress("🔎", "starting", "Reviewing research output for quality and accuracy...")

        build_output = self._load_latest_build()

        prompt = (
            "You are the verifier agent. Critically review the research output below. "
            "Check for: unsupported claims, logical errors, missing evidence, shallow analysis, "
            "and anything that would undermine confidence in the findings. "
            "Issue a verdict (PASS / NEEDS REVISION / FAIL), a confidence score (0–100), "
            "and specific actionable findings.\n\n"
            f"## Research Output to Review\n\n{build_output}"
        )

        if dry_run:
            report_content = "_Dry-run mode — no Claude call made._"
        else:
            report_content = self.call_claude(prompt)

        report_path = self.write_report("Verification Report", report_content)

        # Extract verdict for Slack
        verdict = "Review complete."
        for line in report_content.split("\n"):
            if any(word in line for word in ["PASS", "FAIL", "NEEDS REVISION", "confidence", "Confidence"]):
                verdict = line.strip().lstrip("#").strip()[:200]
                break
        self.post_slack_progress("✅", "done", verdict)

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    VerifierAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
