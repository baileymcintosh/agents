"""
Debugger agent — two modes:

1. INLINE (primary): Called by a struggling agent mid-run.
   Analyzes the error, suggests a fix, and lets the agent retry.
   The pipeline never stops.

2. POST-FAILURE (fallback): Triggered by GitHub Actions when a job crashes
   completely. Diagnoses and posts to Slack.
"""

from __future__ import annotations

import os
import subprocess
import traceback
from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config


class DebuggerAgent(BaseAgent):
    role = "debugger"

    def __init__(self) -> None:
        super().__init__()
        self.model = config.VERIFIER_MODEL  # Sonnet is sufficient for debugging
        self.run_id = os.getenv("GITHUB_RUN_ID", "")
        self.repo = os.getenv("GITHUB_REPOSITORY", config.GITHUB_REPO)

    # ── Inline recovery (primary mode) ────────────────────────────────────────

    def consult(
        self,
        agent_role: str,
        error: Exception,
        original_prompt: str,
        attempt: int = 1,
    ) -> dict[str, Any]:
        """
        Called by a struggling agent mid-run. Returns one of:
        - {"action": "retry", "modified_prompt": "..."} — agent should retry with this
        - {"action": "escalate", "message": "..."} — cannot fix, notify Slack and stop

        Args:
            agent_role: which agent is struggling (planner, builder, etc.)
            error: the exception that was raised
            original_prompt: the prompt the agent was using when it failed
            attempt: how many times we've already tried
        """
        error_text = f"{type(error).__name__}: {str(error)}"
        tb = traceback.format_exc()[-2000:]

        logger.info(f"[debugger] Consulting on {agent_role} failure (attempt {attempt}): {error_text}")
        self.post_slack_progress(
            "🔧", "consulting",
            f"The {agent_role} hit a problem — diagnosing and attempting recovery... (attempt {attempt})"
        )

        # Hard stop after 3 attempts to avoid infinite loops
        if attempt >= 3:
            message = (
                f"The {agent_role} failed {attempt} times and I cannot automatically fix it. "
                f"Last error: {error_text}"
            )
            self.post_slack_progress("🚨", "escalating", message)
            return {"action": "escalate", "message": message}

        prompt = (
            f"You are the debugger agent. The {agent_role} agent is struggling mid-run.\n\n"
            f"## Error\n```\n{error_text}\n```\n\n"
            f"## Stack Trace\n```\n{tb}\n```\n\n"
            f"## Original Prompt (what the agent was trying to do)\n{original_prompt[:2000]}\n\n"
            "Diagnose the root cause and decide:\n\n"
            "Option A — If this is recoverable: respond with exactly:\n"
            "ACTION: RETRY\n"
            "MODIFIED_PROMPT: <a revised version of the prompt that avoids the problem>\n"
            "REASON: <one sentence explaining what you changed and why>\n\n"
            "Option B — If this cannot be fixed automatically: respond with exactly:\n"
            "ACTION: ESCALATE\n"
            "MESSAGE: <plain English explanation for a non-technical executive>\n\n"
            "Common recoverable errors:\n"
            "- Rate limits → suggest breaking the task into smaller chunks\n"
            "- Content too long → suggest summarizing or focusing on one sub-topic\n"
            "- Web search returned no results → suggest different search terms\n"
            "- Timeout → suggest a simpler version of the task\n\n"
            "Common non-recoverable errors:\n"
            "- Missing API keys → escalate\n"
            "- Authentication failures → escalate\n"
            "- Repeated identical failures → escalate"
        )

        response = self.call_claude(prompt)

        # Parse the response
        if "ACTION: RETRY" in response:
            # Extract the modified prompt
            modified_prompt = original_prompt  # fallback
            reason = ""
            for line in response.split("\n"):
                if line.startswith("MODIFIED_PROMPT:"):
                    modified_prompt = line.replace("MODIFIED_PROMPT:", "").strip()
                elif line.startswith("REASON:"):
                    reason = line.replace("REASON:", "").strip()

            # Handle multiline modified prompts
            if "MODIFIED_PROMPT:" in response and "REASON:" in response:
                start = response.index("MODIFIED_PROMPT:") + len("MODIFIED_PROMPT:")
                end = response.index("REASON:")
                modified_prompt = response[start:end].strip()

            self.post_slack_progress(
                "🔄", "retrying",
                f"Found a fix for the {agent_role}. Retrying with adjusted approach. {reason}"
            )
            return {"action": "retry", "modified_prompt": modified_prompt, "reason": reason}

        elif "ACTION: ESCALATE" in response:
            message = ""
            for line in response.split("\n"):
                if line.startswith("MESSAGE:"):
                    message = line.replace("MESSAGE:", "").strip()
            if not message:
                message = f"The {agent_role} failed and I could not automatically recover it."

            self.post_slack_progress("🚨", "escalating", message)
            return {"action": "escalate", "message": message}

        else:
            # Ambiguous response — escalate to be safe
            self.post_slack_progress(
                "🚨", "escalating",
                f"The {agent_role} failed and the diagnosis was inconclusive. Last error: {error_text}"
            )
            return {"action": "escalate", "message": f"Unresolved failure in {agent_role}: {error_text}"}

    # ── Post-failure mode (GitHub Actions fallback) ───────────────────────────

    def _fetch_failure_logs(self) -> str:
        """Pull failed job logs from GitHub Actions via gh CLI."""
        if not self.run_id:
            return "No GITHUB_RUN_ID — cannot fetch logs automatically."
        try:
            result = subprocess.run(
                ["gh", "run", "view", self.run_id, "--log-failed", "--repo", self.repo],
                capture_output=True, text=True, timeout=30,
            )
            logs = result.stdout if result.returncode == 0 else result.stderr
            return logs[-6000:] if len(logs) > 6000 else logs
        except Exception as e:
            return f"Could not fetch logs: {e}"

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        """Post-failure mode — runs as a GitHub Actions job when the pipeline crashes."""
        logger.info("[debugger] Post-failure mode: pipeline job crashed.")
        self.post_slack_progress(
            "⚠️", "activated",
            "A pipeline crash was detected. Fetching logs and diagnosing..."
        )

        logs = self._fetch_failure_logs()

        if dry_run:
            report_path = self.write_report("Debug Report", "_Dry-run mode._")
            return {"status": "dry_run", "report": str(report_path)}

        prompt = (
            "A GitHub Actions pipeline job has crashed completely. "
            "Read the logs and produce a concise failure report:\n\n"
            "1. **Root Cause** — one sentence\n"
            "2. **Plain English** — what this means for a non-technical executive\n"
            "3. **Severity** — SELF-HEALING / SIMPLE FIX / NEEDS INVESTIGATION\n"
            "4. **Action Required** — exactly what should be done\n\n"
            f"## Failure Logs\n```\n{logs}\n```"
        )

        diagnosis = self.call_claude(prompt)
        report_path = self.write_report("Pipeline Crash Report", diagnosis)

        # Extract severity for emoji
        emoji = "🔄" if "SELF-HEALING" in diagnosis else "🔧" if "SIMPLE FIX" in diagnosis else "🚨"
        self.post_slack_progress(emoji, "diagnosis complete", diagnosis[:500])

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    DebuggerAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
