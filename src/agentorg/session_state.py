"""
Session persistence — tracks active projects across conversations.

Written to both the agents repo (SESSION.md for human readability)
and a JSON file for machine reading. Claude Code reads this at the
start of each conversation to know where we left off.
"""

from __future__ import annotations

import json
import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from agentorg import config

SESSION_FILE = config.ROOT_DIR / "SESSION.json"
SESSION_MD = config.ROOT_DIR / "SESSION.md"


@dataclass
class ProjectSession:
    name: str
    brief: str
    project_dir: str
    github_repo: str = ""          # e.g. "baileymcintosh/iran-war-2026"
    github_url: str = ""           # full https URL
    phase: str = "planning"        # planning | prelim | deep | done
    team: list[str] = field(default_factory=list)   # agent roles in use
    completed_phases: list[str] = field(default_factory=list)
    last_run: str = ""
    last_outputs: list[str] = field(default_factory=list)  # file paths / URLs produced
    pending_feedback: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ProjectSession":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})  # type: ignore[attr-defined]


def save(session: ProjectSession) -> None:
    """Persist session to JSON + human-readable Markdown."""
    session.last_run = datetime.datetime.now().isoformat()
    SESSION_FILE.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
    _write_md(session)


def load() -> ProjectSession | None:
    """Load active session, or None if no session exists."""
    if not SESSION_FILE.exists():
        return None
    try:
        data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        return ProjectSession.from_dict(data)
    except Exception:
        return None


def clear() -> None:
    """Mark session as done and clear state."""
    session = load()
    if session:
        session.phase = "done"
        save(session)


def _write_md(s: ProjectSession) -> None:
    phase_emoji = {"planning": "🗺️", "prelim": "🔍", "deep": "🔬", "done": "✅"}.get(s.phase, "⏳")
    lines = [
        "# Active Session",
        "",
        f"**Project:** {s.name}  ",
        f"**Phase:** {phase_emoji} {s.phase}  ",
        f"**Last run:** {s.last_run[:16].replace('T', ' ')}  ",
    ]
    if s.github_url:
        lines.append(f"**Repo:** {s.github_url}  ")
    if s.team:
        lines.append(f"**Team:** {', '.join(s.team)}  ")
    lines += ["", "## Brief", s.brief, ""]
    if s.last_outputs:
        lines += ["## Latest Outputs"]
        for o in s.last_outputs[-5:]:
            lines.append(f"- {o}")
        lines.append("")
    if s.pending_feedback:
        lines += ["## Pending Feedback", s.pending_feedback, ""]
    if s.notes:
        lines += ["## Notes", s.notes, ""]
    SESSION_MD.write_text("\n".join(lines), encoding="utf-8")
