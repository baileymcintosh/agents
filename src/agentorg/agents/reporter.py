"""Reporter agent — bundles findings into an executive summary and posts to Slack."""

from __future__ import annotations

from typing import Any

from loguru import logger

from agentorg.agents.base import BaseAgent
from agentorg import config





class ReporterAgent(BaseAgent):
    role = "reporter"

    def __init__(self) -> None:
        super().__init__()
        self.model = config.REPORTER_MODEL

    def _gather_recent_reports(self) -> str:
        """Collect the latest planner, builder, and verifier reports."""
        sections = []
        for agent_role in ("planner", "builder", "verifier"):
            files = sorted(
                config.REPORTS_DIR.glob(f"*_{agent_role}_*.md"),
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if files:
                sections.append(f"## {agent_role.capitalize()} Report\n\n{files[0].read_text(encoding='utf-8')}")
        return "\n\n---\n\n".join(sections) if sections else "No reports found."

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        logger.info("[reporter] Building executive summary.")
        context = self._gather_recent_reports()

        prompt = (
            "You are the reporter agent. Based on the reports below, write a concise "
            "executive summary for a non-technical leader. Use plain language. Include:\n"
            "- What the team accomplished this cycle\n"
            "- Key findings or insights\n"
            "- Any risks or blockers\n"
            "- Recommended next steps\n"
            "Keep it to one page. Use bullet points and bold headers.\n\n"
            f"{context}"
        )

        if dry_run:
            summary = "_Dry-run mode — no Claude call made._"
        else:
            summary = self.call_claude(prompt)

        report_path = self.write_report("Executive Summary", summary)

        # Post to Slack if configured
        if config.SLACK_BOT_TOKEN and config.SLACK_EXECUTIVE_CHANNEL_ID and not dry_run:
            from agentorg.slack_bot.client import SlackClient
            slack = SlackClient()
            slack.post_message(
                channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                text=f"*Executive Summary — {report_path.stem}*\n\n{summary[:2900]}",
            )
            slack.upload_file(
                channel=config.SLACK_EXECUTIVE_CHANNEL_ID,
                file_path=str(report_path),
                title=report_path.stem,
            )

        return {"status": "ok", "report": str(report_path)}


def main(dry_run: bool = False) -> None:
    ReporterAgent().run(dry_run=dry_run)


if __name__ == "__main__":
    main()
