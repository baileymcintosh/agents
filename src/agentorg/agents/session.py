"""
Collaborative Research Session — runs qual and quant builders in parallel threads
with a shared message bus so they can question and answer each other in real time.

Flow per cycle:
  - Both agents start simultaneously as threads
  - Each runs N turns, checking for partner messages before every turn
  - When quant spots a data anomaly it posts a question → qual searches for context
  - When qual finds a key event it posts a data request → quant verifies in the data
  - After all turns, both write consolidated reports
  - Reporter synthesises everything at the end
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from loguru import logger

from agentorg import config
from agentorg.messaging import AgentMessenger
from agentorg.timing import RunClock


class CollaborativeSession:
    """
    Orchestrates parallel qual + quant research with inter-agent messaging.

    Usage:
        session = CollaborativeSession(research_plan, clock=RunClock.load())
        session.run(turns_per_agent=3)
    """

    def __init__(self, research_plan: str, clock: RunClock | None = None) -> None:
        self.research_plan = research_plan
        self.clock = clock
        self.messenger = AgentMessenger(config.REPORTS_DIR)
        self._qual_error: Exception | None = None
        self._quant_error: Exception | None = None

    def run(self, turns_per_agent: int | None = None) -> dict[str, Any]:
        """
        Run the collaborative session.

        Args:
            turns_per_agent: How many research turns each agent takes.
                             If None, uses config.SESSION_COLLAB_TURNS.
        """
        turns = turns_per_agent or config.SESSION_COLLAB_TURNS
        logger.info(f"[session] Starting collaborative session — {turns} turns per agent")

        # Import here to avoid circular imports at module load
        from agentorg.agents.qual_builder import QualBuilderAgent
        from agentorg.agents.quant_builder import QuantBuilderAgent

        qual = QualBuilderAgent()
        quant = QuantBuilderAgent()

        completed_sections: list[str] = []

        qual_thread = threading.Thread(
            target=self._run_qual_loop,
            args=(qual, turns, completed_sections),
            name="qual-builder",
            daemon=True,
        )
        quant_thread = threading.Thread(
            target=self._run_quant_loop,
            args=(quant, turns),
            name="quant-builder",
            daemon=True,
        )

        logger.info("[session] Launching qual (OpenAI) and quant (Claude) in parallel...")
        qual_thread.start()
        quant_thread.start()

        qual_thread.join()
        quant_thread.join()

        if self._qual_error:
            logger.error(f"[session] Qual builder failed: {self._qual_error}")
        if self._quant_error:
            logger.error(f"[session] Quant builder failed: {self._quant_error}")

        # Write consolidated reports
        qual_report = qual.write_consolidated_report()
        quant_report = quant.write_consolidated_report()

        # Write the full cross-agent dialogue as its own report
        dialogue_path = self._write_dialogue_report()

        all_charts = quant._all_charts
        logger.info(
            f"[session] Complete — {turns} turns each, "
            f"{len(all_charts)} charts, "
            f"{len(self.messenger.all_messages())} cross-agent messages"
        )

        return {
            "qual_report": str(qual_report),
            "quant_report": str(quant_report),
            "dialogue_report": str(dialogue_path),
            "charts": all_charts,
            "messages": len(self.messenger.all_messages()),
        }

    def _run_qual_loop(
        self,
        qual: Any,
        turns: int,
        completed_sections: list[str],
    ) -> None:
        try:
            for turn in range(1, turns + 1):
                if self._time_exhausted():
                    logger.info(f"[qual] Time budget exhausted at turn {turn} — stopping")
                    break

                clock_ctx = self.clock.prompt_context("qual_builder") if self.clock else ""

                logger.info(f"[qual] Starting turn {turn}/{turns}")
                findings = qual.run_turn(
                    turn=turn,
                    research_plan=self.research_plan,
                    messenger=self.messenger,
                    completed_sections=completed_sections,
                    clock_context=clock_ctx,
                )
                qual.write_report(turn, findings)

                # Small stagger so turns don't always land simultaneously
                time.sleep(2)

        except Exception as e:
            self._qual_error = e
            logger.exception(f"[qual] Loop crashed: {e}")

    def _run_quant_loop(self, quant: Any, turns: int) -> None:
        # Slight delay so qual gets a head start and can post initial findings
        # before quant's first turn — gives quant something to cross-reference
        time.sleep(5)

        try:
            for turn in range(1, turns + 1):
                if self._time_exhausted():
                    logger.info(f"[quant] Time budget exhausted at turn {turn} — stopping")
                    break

                clock_ctx = self.clock.prompt_context("quant_builder") if self.clock else ""

                logger.info(f"[quant] Starting turn {turn}/{turns}")
                findings, charts = quant.run_turn(
                    turn=turn,
                    research_plan=self.research_plan,
                    messenger=self.messenger,
                    clock_context=clock_ctx,
                )
                quant.write_report(turn, findings, charts)

                time.sleep(2)

        except Exception as e:
            self._quant_error = e
            logger.exception(f"[quant] Loop crashed: {e}")

    def _time_exhausted(self) -> bool:
        if not self.clock:
            return False
        remaining = self.clock.remaining_seconds()
        # Stop agent loops if less than 3 minutes left (reserve for reporter)
        return remaining < 180

    def _write_dialogue_report(self) -> Path:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = config.REPORTS_DIR / f"{timestamp}_session_dialogue.md"
        content = (
            f"# Qual ↔ Quant Research Dialogue\n\n"
            f"*Auto-generated cross-agent conversation log*\n\n"
            f"---\n\n"
            f"{self.messenger.format_full_dialogue()}"
        )
        path.write_text(content, encoding="utf-8")
        logger.info(f"[session] Dialogue log → {path.name}")
        return path


def run_collaborative_session(
    time_budget: str = "",
    turns_per_agent: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Entry point called by the CLI `agentorg session` command.

    1. Loads (or initialises) RunClock from the time budget
    2. Loads the latest planner report as the research plan
    3. Runs CollaborativeSession
    4. Runs Reporter to synthesise everything
    """
    import os
    from agentorg.timing import RunClock

    # Set time budget in env so agents pick it up
    if time_budget:
        os.environ["TIME_BUDGET"] = time_budget
        import agentorg.config as _cfg
        _cfg.TIME_BUDGET = time_budget

    clock = RunClock.load()
    if clock is None and time_budget:
        clock = RunClock.initialize(time_budget)

    # Load the latest planner report
    plan_files = sorted(
        config.REPORTS_DIR.glob("*_planner_*.md"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not plan_files:
        raise RuntimeError("No planner report found — run the planner first.")
    research_plan = plan_files[0].read_text(encoding="utf-8")
    logger.info(f"[session] Using plan: {plan_files[0].name}")

    if dry_run:
        logger.info("[session] Dry-run mode — skipping agent calls")
        return {"status": "dry_run"}

    session = CollaborativeSession(research_plan=research_plan, clock=clock)
    result = session.run(turns_per_agent=turns_per_agent)

    # Run reporter to synthesise qual + quant outputs
    logger.info("[session] Running reporter...")
    from agentorg.agents.reporter import ReporterAgent
    reporter = ReporterAgent()
    reporter_result = reporter.run(dry_run=False)
    result["reporter"] = reporter_result

    return result
