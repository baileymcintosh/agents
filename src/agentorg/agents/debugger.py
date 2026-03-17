"""
Debugger agent — activates only when another agent fails.

Reads GitHub Actions failure logs, diagnoses the root cause via Claude,
posts a plain-English explanation to Slack, and attempts simple fixes.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config


# Errors the debugger can resolve automatically without human input
AUTO_FIXABLE = {
    "RateLimitError": (
        "rate_limit",
        "Hit Anthropic API rate limit. This is automatically handled by the retry logic. "
        "If it keeps happening, add billing credits at console.anthropic.com to reach Tier 2."
    ),
    "failed to push some refs": (
        "git_conflict",
        "Git push conflict — two jobs tried to push at the same time. "
        "Fixed by pull-before-push logic already in place. Safe to re-run."
    ),
    "not_in_channel": (
        "slack_channel",
        "Slack bot is not a member of the channel. "
        "Fix: in Slack, type /invite @AgentOrg in the target channel."
    ),
    "ModuleNotFoundError": (
        "missing_module",
        "A Python package is missing. This usually means pyproject.toml needs updating."
    ),
    "FileNotFoundError": (
        "missing_file",
        "A required file was not found. Check that all previous agents ran successfully."
    ),
    "ANTHROPIC_API_KEY": (
        "missing_key",
        "Anthropic API key is missing or invalid. "
        "Check GitHub Secrets → ANTHROPIC_API_KEY is set correctly."
    ),
    "TAVILY_API_KEY": (
        "missing_key",
        "Tavily API key is missing. Web search is disabled. "
        "Add TAVILY_API_KEY to GitHub Secrets, or the agents will run without web search."
    ),
}


class DebuggerAgent(BaseAgent):
    role = "debugger"

    def __init__(self) -> None:
        super().__init__()
        self.model = config.VERIFIER_MODEL  # Sonnet is fine for debugging
        self.run_id = os.getenv("GITHUB_RUN_ID", "")
        self.repo = os.getenv("GITHUB_REPOSITORY", config.GITHUB_REPO)

    def _fetch_failure_logs(self) -> str:
        """Pull the failed job logs from GitHub Actions via gh CLI."""
        if not self.run_id:
            return "No GITHUB_RUN_ID available — cannot fetch logs."

        try:
            result = subprocess.run(
                ["gh", "run", "view", self.run_id, "--log-failed", "--repo", self.repo],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Trim to last 6000 chars to stay within token limits
                logs = result.stdout[-6000:] if len(result.stdout) > 6000 else result.stdout
                return logs
            else:
                return f"Could not fetch logs: {result.stderr[:500]}"
        except Exception as e:
            return f"Error fetching logs: {e}"

    def _quick_diagnose(self, logs: str) -> tuple[str, str] | None:
        """
        Check if the error matches a known pattern we can explain immediately.
        Returns (error_type, plain_english_explanation) or None if unknown.
        """
        for pattern, (error_type, explanation) in AUTO_FIXABLE.items():
            if pattern in logs:
                return error_type, explanation
        return None

    def _diagnose_with_claude(self, logs: str) -> str:
        """Ask Claude to diagnose an unknown failure in plain English."""
        prompt = (
            "You are a debugging assistant for an autonomous AI research pipeline. "
            "A GitHub Actions job has failed. Read the logs below and provide:\n\n"
            "1. **Root Cause** — What went wrong, in one sentence\n"
            "2. **Plain English Explanation** — What this means for a non-technical person\n"
            "3. **Severity** — Is this: SELF-HEALING (will fix itself on retry) / "
            "SIMPLE FIX (needs one small change) / NEEDS INVESTIGATION (unclear)\n"
            "4. **Recommended Action** — Exactly what should be done next\n\n"
            "Be concise. The output goes directly to Slack.\n\n"
            f"## Failure Logs\n\n```\n{logs}\n```"
        )
        return self.call_claude(prompt)

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[debugger] Pipeline failure detected — starting diagnosis.")

        # Post immediate acknowledgement to Slack
        self.post_slack_progress(
            "⚠️", "activated",
            "A pipeline failure was detected. Fetching logs and diagnosing now..."
        )

        # Fetch the failure logs
        logs = self._fetch_failure_logs()
        logger.info(f"[debugger] Fetched {len(logs)} chars of failure logs")

        if dry_run:
            diagnosis = "_Dry-run mode — no diagnosis performed._"
            self.post_slack_progress("🔧", "dry-run", diagnosis)
            return {"status": "dry_run"}

        # Try quick pattern match first
        quick = self._quick_diagnose(logs)

        if quick:
            error_type, explanation = quick
            logger.info(f"[debugger] Known error type: {error_type}")
            diagnosis = explanation
            severity = "SELF-HEALING" if error_type in ("rate_limit", "git_conflict") else "SIMPLE FIX"
        else:
            # Unknown error — ask Claude
            logger.info("[debugger] Unknown error — consulting Claude for diagnosis")
            diagnosis = self._diagnose_with_claude(logs)
            severity = "NEEDS INVESTIGATION"

        # Write a full debug report
        report_content = (
            f"## Pipeline Failure Report\n\n"
            f"**Run ID:** {self.run_id}\n"
            f"**Severity:** {severity}\n\n"
            f"### Diagnosis\n\n{diagnosis}\n\n"
            f"### Raw Logs (last 3000 chars)\n\n```\n{logs[-3000:]}\n```"
        )
        report_path = self.write_report("Debug Report", report_content)

        # Post detailed Slack update
        emoji = "🔄" if severity == "SELF-HEALING" else "🔧" if severity == "SIMPLE FIX" else "🚨"
        slack_message = f"*{severity}*\n{diagnosis[:600]}"
        self.post_slack_progress(emoji, f"diagnosis complete", slack_message)

        logger.info(f"[debugger] Diagnosis complete. Severity: {severity}")
        return {"status": "ok", "severity": severity, "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    DebuggerAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
