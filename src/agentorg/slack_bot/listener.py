"""
Slack listener — polls the executive channel for commands and triggers agent runs.

Supported commands (post in Slack channel, or reply to any message):
  run all         — trigger the full nightly pipeline
  run planner     — trigger planner only
  run builder     — trigger builder only
  run verifier    — trigger verifier only
  run reporter    — trigger reporter only
  run fast        — run full pipeline in fast mode (all Sonnet, short output)
  status          — list recent reports
  help            — show available commands

The listener is invoked by a GitHub Actions workflow on a schedule.
It checks for messages posted in the last LOOKBACK_MINUTES minutes that
are not from the bot itself.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from loguru import logger

from agentorg import config


LOOKBACK_MINUTES = 12  # check messages from the last N minutes (accounts for schedule drift)

HELP_TEXT = """\
:robot_face: *AgentOrg commands*

• `run session 2h` — *recommended* — multi-cycle deep research for a set duration
• `run session 20h` — overnight world-class research (runs until done or time up)
• `run fast 5m` — quick brief with web search, all agents in ~5 min
• `run all` — single full pipeline cycle (Opus, deep mode)
• `run planner` / `run builder` / `run verifier` / `run reporter` — individual agents
• `status` — show recent reports
• `help` — show this message

*Time budget examples:* `5m` = 5 min · `30m` = 30 min · `2h` = 2 hours · `20h` = 20 hours
"""

BASE_COMMANDS = {
    "run session": ("research_session.yml", {}),   # multi-cycle — time_budget appended from message
    "run all": ("nightly.yml", {}),
    "run fast": ("nightly.yml", {"fast_mode": "true"}),
    "run planner": ("run_agent.yml", {"agent": "planner"}),
    "run builder": ("run_agent.yml", {"agent": "builder"}),
    "run verifier": ("run_agent.yml", {"agent": "verifier"}),
    "run reporter": ("run_agent.yml", {"agent": "reporter"}),
}


class SlackListener:
    def __init__(self) -> None:
        if not config.SLACK_BOT_TOKEN:
            raise RuntimeError("SLACK_BOT_TOKEN not set")
        self.token = config.SLACK_BOT_TOKEN
        self.channel = config.SLACK_EXECUTIVE_CHANNEL_ID
        self.bot_user_id = config.SLACK_BOT_USER_ID
        self.repo = config.GITHUB_REPO or os.getenv("GITHUB_REPOSITORY", "")
        self.gh_token = config.GITHUB_TOKEN or os.getenv("GH_TOKEN", "")

    def _slack_get(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        resp = httpx.get(
            f"https://slack.com/api/{method}",
            headers={"Authorization": f"Bearer {self.token}"},
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error ({method}): {data.get('error')}")
        return data  # type: ignore[return-value]

    def _slack_post(self, text: str, thread_ts: str | None = None) -> None:
        payload: dict[str, Any] = {"channel": self.channel, "text": text}
        if thread_ts:
            payload["thread_ts"] = thread_ts
        resp = httpx.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            content=json.dumps(payload),
            timeout=10,
        )
        resp.raise_for_status()

    def _get_recent_messages(self) -> list[dict[str, Any]]:
        """Fetch channel messages from the last LOOKBACK_MINUTES minutes."""
        oldest = str(time.time() - LOOKBACK_MINUTES * 60)
        data = self._slack_get(
            "conversations.history",
            {"channel": self.channel, "oldest": oldest, "limit": 20},
        )
        return data.get("messages", [])  # type: ignore[return-value]

    def _trigger_workflow(self, workflow_file: str, inputs: dict[str, str]) -> bool:
        """Dispatch a GitHub Actions workflow via the gh CLI."""
        if not self.repo:
            logger.error("[listener] GITHUB_REPO not set — cannot trigger workflow")
            return False

        cmd = ["gh", "workflow", "run", workflow_file, "--repo", self.repo]
        for key, val in inputs.items():
            cmd += ["-f", f"{key}={val}"]

        env = os.environ.copy()
        if self.gh_token:
            env["GH_TOKEN"] = self.gh_token

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=30)
            if result.returncode == 0:
                logger.info(f"[listener] Triggered {workflow_file} with {inputs}")
                return True
            logger.error(f"[listener] gh workflow run failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"[listener] Workflow dispatch error: {e}")
            return False

    def _get_status(self) -> str:
        """List the 5 most recent report files."""
        if not config.REPORTS_DIR.exists():
            return "No reports directory found yet."
        files = sorted(config.REPORTS_DIR.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)[:5]
        if not files:
            return "No reports found yet."
        lines = ["*Recent reports:*"]
        for f in files:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            lines.append(f"• `{f.name}` — {mtime}")
        return "\n".join(lines)

    def process_messages(self) -> None:
        """Check recent messages and act on any commands."""
        messages = self._get_recent_messages()
        logger.info(f"[listener] Found {len(messages)} recent message(s)")

        for msg in messages:
            # Skip messages from the bot itself
            if self.bot_user_id and msg.get("user") == self.bot_user_id:
                continue
            # Skip bot messages in general (subtype = bot_message)
            if msg.get("subtype") == "bot_message":
                continue

            text = msg.get("text", "").strip().lower()
            ts = msg.get("ts")

            # Check for commands
            if text == "help":
                self._slack_post(HELP_TEXT, thread_ts=ts)
                continue

            if text == "status":
                self._slack_post(self._get_status(), thread_ts=ts)
                continue

            for command, (workflow, inputs) in BASE_COMMANDS.items():
                # Support optional time budget suffix: "run fast 5m", "run all 2h"
                if text == command or text.startswith(command + " "):
                    # Extract optional time budget suffix: "run fast 5m", "run session 2h"
                    extra = text[len(command):].strip()
                    run_inputs = dict(inputs)
                    budget_display = ""
                    if extra:
                        run_inputs["time_budget"] = extra
                        budget_display = f" (budget: {extra})"
                    elif command == "run session":
                        # run session requires a time budget
                        self._slack_post(
                            ":x: `run session` requires a time budget. Example: `run session 2h`",
                            thread_ts=ts,
                        )
                        break

                    self._slack_post(
                        f":hourglass_flowing_sand: Got it — triggering `{command}`{budget_display}...",
                        thread_ts=ts,
                    )
                    success = self._trigger_workflow(workflow, run_inputs)
                    if success:
                        self._slack_post(
                            f":white_check_mark: `{command}` dispatched. You'll get Slack updates as it runs.",
                            thread_ts=ts,
                        )
                    else:
                        self._slack_post(
                            f":x: Failed to trigger `{command}`. Check GitHub Actions logs.",
                            thread_ts=ts,
                        )
                    break


def main() -> None:
    listener = SlackListener()
    listener.process_messages()


if __name__ == "__main__":
    main()
