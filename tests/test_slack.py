"""Tests for Slack client (uses mocks — no real API calls)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_slack_client_raises_without_token() -> None:
    with patch("agentorg.config.SLACK_BOT_TOKEN", ""):
        from agentorg.slack_bot.client import SlackClient
        with pytest.raises(RuntimeError, match="SLACK_BOT_TOKEN"):
            SlackClient()


def test_slack_post_message(tmp_path: Path) -> None:
    with patch("agentorg.config.SLACK_BOT_TOKEN", "xoxb-fake"), \
         patch("agentorg.config.SLACK_EXECUTIVE_CHANNEL_ID", "C123"), \
         patch("slack_sdk.WebClient") as MockClient:

        mock_client = MagicMock()
        MockClient.return_value = mock_client
        mock_client.chat_postMessage.return_value.data = {"ok": True, "ts": "123"}

        from agentorg.slack_bot.client import SlackClient
        slack = SlackClient()
        result = slack.post_message("C123", "Hello from tests!")

        mock_client.chat_postMessage.assert_called_once()
        call_kwargs = mock_client.chat_postMessage.call_args.kwargs
        assert call_kwargs["channel"] == "C123"
        assert call_kwargs["text"] == "Hello from tests!"


def test_slack_upload_file_raises_on_missing_file(tmp_path: Path) -> None:
    with patch("agentorg.config.SLACK_BOT_TOKEN", "xoxb-fake"), \
         patch("slack_sdk.WebClient"):
        from agentorg.slack_bot.client import SlackClient
        slack = SlackClient()
        with pytest.raises(FileNotFoundError):
            slack.upload_file("C123", "/nonexistent/file.pdf")
