"""
Inter-agent message bus for collaborative research sessions.

Qual and quant builders use this to ask each other questions and share findings
in real time while running as parallel threads.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from loguru import logger


MessageType = Literal["question", "finding", "answer", "data_point"]


@dataclass
class AgentMessage:
    id: str
    from_agent: str          # "qual" or "quant"
    to_agent: str            # "qual" or "quant"
    message_type: MessageType
    content: str
    timestamp: float = field(default_factory=time.time)
    read: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentMessage":
        return cls(**d)


class AgentMessenger:
    """
    Thread-safe message bus shared between qual and quant builders.

    Both agents run as threads and call post() / drain() concurrently.
    Messages are also persisted to disk so the session log is readable.
    """

    def __init__(self, session_dir: Path | None = None, run_id: str | None = None) -> None:
        self._lock = threading.Lock()
        self._messages: list[AgentMessage] = []
        if session_dir is None:
            import tempfile
            session_dir = Path(tempfile.mkdtemp())
        self._log_path = session_dir / "agent_messages.json"
        session_dir.mkdir(parents=True, exist_ok=True)

    def post(self, from_agent: str, to_agent: str, message_type: MessageType, content: str) -> AgentMessage:
        msg = AgentMessage(
            id=str(uuid.uuid4())[:8],
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content,
        )
        with self._lock:
            self._messages.append(msg)
            self._persist()
        logger.info(f"[{from_agent}→{to_agent}] {message_type}: {content[:120]}")
        return msg

    def drain(self, recipient: str) -> list[AgentMessage]:
        """Return all unread messages for recipient and mark them read."""
        with self._lock:
            unread = [m for m in self._messages if m.to_agent == recipient and not m.read]
            for m in unread:
                m.read = True
            if unread:
                self._persist()
        return unread

    def all_messages(self) -> list[AgentMessage]:
        with self._lock:
            return list(self._messages)

    def format_for_prompt(self, messages: list[AgentMessage]) -> str:
        """Format a list of messages as a readable block to inject into a prompt."""
        if not messages:
            return ""
        lines = ["## Messages from your research partner\n"]
        for m in messages:
            prefix = f"[{m.from_agent.upper()} → {m.to_agent.upper()}] ({m.message_type})"
            lines.append(f"**{prefix}**\n{m.content}\n")
        return "\n".join(lines)

    def format_full_dialogue(self) -> str:
        """Full cross-agent dialogue for the reporter to include in synthesis."""
        msgs = self.all_messages()
        if not msgs:
            return "No cross-agent dialogue recorded."
        lines = ["## Qual ↔ Quant Research Dialogue\n"]
        for m in sorted(msgs, key=lambda x: x.timestamp):
            ts = time.strftime("%H:%M:%S", time.localtime(m.timestamp))
            lines.append(f"**[{ts}] {m.from_agent.upper()} → {m.to_agent.upper()} ({m.message_type})**\n{m.content}\n")
        return "\n".join(lines)

    def _persist(self) -> None:
        try:
            self._log_path.write_text(
                json.dumps([m.to_dict() for m in self._messages], indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"[messenger] Failed to persist messages: {e}")
