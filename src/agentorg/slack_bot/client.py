"""Slack client — thin wrapper around slack-sdk for agent use."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from agentorg import config


# Maps logical channel names to Slack channel IDs from config
CHANNEL_MAP: dict[str, str] = {
    "executive": config.SLACK_EXECUTIVE_CHANNEL_ID,
    "engineering": config.SLACK_ENGINEERING_CHANNEL_ID,
    "alerts": config.SLACK_ALERTS_CHANNEL_ID,
}


class SlackClient:
    """
    Wrapper around slack_sdk.WebClient with helpers for the agent system.

    Usage:
        slack = SlackClient()
        slack.post_message("executive", "Hello from the reporter agent!")
        slack.upload_file("engineering", "reports/summary.pdf", title="Weekly Summary")
    """

    def __init__(self) -> None:
        if not config.SLACK_BOT_TOKEN:
            raise RuntimeError(
                "SLACK_BOT_TOKEN is not set. Add it to your .env file. "
                "See .env.example for instructions."
            )
        self.client = WebClient(token=config.SLACK_BOT_TOKEN)

    def _resolve_channel(self, channel: str) -> str:
        """Accept either a logical name ('executive') or a raw channel ID ('C0XXX')."""
        return CHANNEL_MAP.get(channel, channel)

    def post_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Post a plain-text or Block Kit message to a channel."""
        channel_id = self._resolve_channel(channel)
        try:
            kwargs: dict[str, Any] = {"channel": channel_id, "text": text}
            if blocks:
                kwargs["blocks"] = blocks
            response = self.client.chat_postMessage(**kwargs)
            logger.info(f"[slack] Message posted to {channel_id}")
            return dict(response.data)  # type: ignore[arg-type]
        except SlackApiError as e:
            logger.error(f"[slack] Failed to post message: {e.response['error']}")
            raise

    def upload_file(
        self,
        channel: str,
        file_path: str,
        title: str = "",
        initial_comment: str = "",
    ) -> dict[str, Any]:
        """Upload a file (e.g., PDF report) to a channel."""
        channel_id = self._resolve_channel(channel)
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            response = self.client.files_upload_v2(
                channel=channel_id,
                file=str(path),
                title=title or path.stem,
                initial_comment=initial_comment,
            )
            logger.info(f"[slack] File uploaded: {path.name} → {channel_id}")
            return dict(response.data)  # type: ignore[arg-type]
        except SlackApiError as e:
            logger.error(f"[slack] Failed to upload file: {e.response['error']}")
            raise

    def post_report_summary(
        self,
        channel: str,
        title: str,
        summary: str,
        report_path: str | None = None,
    ) -> None:
        """Post a formatted report summary and optionally attach the report file."""
        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": title},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": summary[:2900]},
            },
        ]
        self.post_message(channel=channel, text=title, blocks=blocks)

        if report_path:
            self.upload_file(channel=channel, file_path=report_path, title=title)
