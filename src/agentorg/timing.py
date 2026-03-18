"""
RunClock — time budget tracking for the agent pipeline.

At the start of a pipeline run, RunClock.initialize() writes a metadata file
(reports/.run_meta.json) with the start epoch and total budget in minutes.

Every agent reads this file via RunClock.load() to know:
  - How much total time was budgeted
  - How much time has elapsed
  - How much time remains
  - What depth/scope to use given remaining time

This lets agents behave like a punctual human analyst: when time is short,
be concise and direct; when time is ample, go deep.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config

# Depth tiers — maps (min_remaining_minutes, max_searches, max_tokens_hint, guidance)
_TIERS = [
    # (min_remaining, max_searches, token_guidance, prose_guidance)
    (0,   1,  400,  "CRITICAL time constraint. Write a 2-3 sentence summary only. No analysis."),
    (3,   1,  600,  "Very tight time. One focused search. Write 200-400 words max. Key facts only."),
    (8,   2,  900,  "Tight time. Two searches max. Write 400-700 words. Findings + brief rationale."),
    (15,  3, 1200,  "Moderate time. Three searches. Write 700-1200 words. Solid analysis with evidence."),
    (30,  5, 2000,  "Comfortable time. Up to 5 searches. Write 1200-2000 words. Full section analysis."),
    (60,  8, 3500,  "Ample time. Up to 8 searches. Write 2000-3500 words. Deep analysis with precedents and data."),
    (120, 12, 6000, "Generous time. Up to 12 searches. Full Bridgewater-quality research. Exhaustive evidence."),
    (480, 20, 8000, "Full depth. Unlimited searches within reason. Maximum rigor and detail."),
]


def parse_budget_string(s: str) -> float:
    """
    Parse a human-friendly time string into minutes.

    Examples:
        "5m"   → 5.0
        "30m"  → 30.0
        "2h"   → 120.0
        "20h"  → 1200.0
        "1.5h" → 90.0
        "90"   → 90.0   (bare number assumed minutes)
    """
    s = s.strip().lower()
    if s.endswith("h"):
        return float(s[:-1]) * 60
    if s.endswith("m"):
        return float(s[:-1])
    return float(s)  # bare number = minutes


class RunClock:
    """Tracks time budget for a pipeline run."""

    def __init__(self, start_epoch: float, budget_minutes: float) -> None:
        self.start_epoch = start_epoch
        self.budget_minutes = budget_minutes  # 0 = unlimited

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    @classmethod
    def initialize(cls, budget_minutes: float) -> "RunClock":
        """
        Called once at the start of a pipeline run (by the planner or fast job).
        Writes the meta file so all subsequent agents can read it.
        """
        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        start = time.time()
        meta: dict[str, Any] = {"start_epoch": start, "budget_minutes": budget_minutes}
        cls._meta_file().write_text(json.dumps(meta), encoding="utf-8")
        logger.info(f"[clock] Run started. Budget: {budget_minutes:.0f} min")
        return cls(start_epoch=start, budget_minutes=budget_minutes)

    @classmethod
    def load(cls) -> "RunClock | None":
        """
        Load the clock from the meta file written by the first agent.
        Returns None if no budget was set (unlimited run).
        """
        meta_file = cls._meta_file()
        if not meta_file.exists():
            return None
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            budget = float(meta.get("budget_minutes", 0))
            if budget <= 0:
                return None
            return cls(start_epoch=float(meta["start_epoch"]), budget_minutes=budget)
        except Exception as e:
            logger.warning(f"[clock] Could not read run meta: {e}")
            return None

    @staticmethod
    def _meta_file() -> Path:
        return config.REPORTS_DIR / ".run_meta.json"

    # ── Time calculations ──────────────────────────────────────────────────────

    def elapsed_minutes(self) -> float:
        return (time.time() - self.start_epoch) / 60

    def remaining_minutes(self) -> float:
        return max(0.0, self.budget_minutes - self.elapsed_minutes())

    def is_overdue(self) -> bool:
        return self.remaining_minutes() <= 0

    def _tier(self) -> tuple[int, int, str]:
        """Return (max_searches, token_hint, guidance) for remaining time."""
        rem = self.remaining_minutes()
        for min_rem, max_searches, token_hint, guidance in reversed(_TIERS):
            if rem >= min_rem:
                return max_searches, token_hint, guidance
        return 1, 400, _TIERS[0][3]

    def max_searches(self) -> int:
        return self._tier()[0]

    def token_hint(self) -> int:
        return self._tier()[1]

    # ── Prompt injection ───────────────────────────────────────────────────────

    def prompt_context(self, role: str) -> str:
        """
        Returns a block of text to prepend to every agent prompt.
        Tells Claude exactly how much time is left and what depth to use.
        """
        rem = self.remaining_minutes()
        elapsed = self.elapsed_minutes()
        _, _, guidance = self._tier()

        pct_used = elapsed / self.budget_minutes * 100 if self.budget_minutes else 0

        lines = [
            f"\n\n---",
            f"**⏱ Time Budget** | Total: {self.budget_minutes:.0f} min | "
            f"Elapsed: {elapsed:.1f} min | Remaining: {rem:.1f} min ({100 - pct_used:.0f}% left)",
            f"**Depth Calibration:** {guidance}",
            f"You are the {role} agent. Respect this constraint as a professional would. "
            f"A good analyst delivers on time — never over-runs. "
            f"Adjust scope, not quality: be precise and direct, cut breadth before depth.",
            f"---\n",
        ]
        return "\n".join(lines)

    def planner_context(self) -> str:
        """
        Extended context for the planner — helps it allocate time across all pipeline stages.
        Overhead per agent (GitHub Actions setup) is ~30s in fast mode, ~90s in full mode.
        """
        rem = self.remaining_minutes()

        # Rough estimates for what fits in remaining time
        # (Each agent call: fast~45s, normal~3-8min depending on search depth)
        if rem < 2:
            cycles_possible = "ZERO — only a summary wrap-up is feasible"
            instructions = "Do NOT assign the builder new research. Write a final summary of what exists."
        elif rem < 5:
            cycles_possible = "at most 1 very fast cycle (builder + reporter)"
            instructions = "Assign one tightly-scoped question answerable in 2 searches."
        elif rem < 15:
            cycles_possible = "1 solid cycle"
            instructions = "Assign one focused research section. Be specific. Builder has ~5-8 min."
        elif rem < 45:
            cycles_possible = "2-3 cycles"
            instructions = "Assign one full section with clear sub-questions. Moderate depth."
        elif rem < 120:
            cycles_possible = "4-6 cycles"
            instructions = "Assign a full section with depth. Builder can do 5-8 searches."
        else:
            cycles_possible = "many deep cycles"
            instructions = "Plan full Bridgewater-quality depth. Multiple sections per day if budget allows."

        return (
            f"\n\n**Pipeline Time Allocation:**\n"
            f"- Remaining budget: {rem:.1f} min\n"
            f"- Feasible research cycles: {cycles_possible}\n"
            f"- Planning instruction: {instructions}\n"
        )
