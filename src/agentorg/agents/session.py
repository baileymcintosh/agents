"""
Collaborative research session with an explicit agenda and persisted evidence.

The canonical flow is:
  team planner -> collaborative qual/quant session -> verifier -> reporter
"""

from __future__ import annotations

import datetime
import threading
import time
from pathlib import Path
from typing import Any

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config
from agentorg.evidence import AgendaItem, EvidenceStore
from agentorg.messaging import AgentMessenger
from agentorg.timing import RunClock


class CollaborativeSession:
    """Runs qual and quant in parallel until the agenda is exhausted or time runs out."""

    def __init__(
        self,
        research_plan: str,
        agenda_seed: list[str],
        clock: RunClock | None = None,
        max_cycles: int | None = None,
        mode: str = "deep",
    ) -> None:
        self.research_plan = research_plan
        self.clock = clock
        self.mode = mode
        self.max_cycles = max_cycles or config.SESSION_COLLAB_TURNS
        self.agenda_item_cap = max(6, self.max_cycles * 4)
        self.messenger = AgentMessenger(config.REPORTS_DIR)
        self.evidence = EvidenceStore(config.REPORTS_DIR)
        self.evidence.bootstrap_agenda(agenda_seed)
        self._qual_error: Exception | None = None
        self._quant_error: Exception | None = None
        self._lock = threading.Lock()
        self._qual_turn1_done = threading.Event()
        self._quant_turn1_done = threading.Event()
        self._critic_done = threading.Event()
        self._critic_result: dict[str, Any] | None = None

    def run(self) -> dict[str, Any]:
        logger.info(
            f"[session] Starting collaborative session — max {self.max_cycles} agenda cycles"
        )

        from agentorg.agents.qual_builder import QualBuilderAgent
        from agentorg.agents.quant_builder import QuantBuilderAgent

        qual = QualBuilderAgent()
        quant = QuantBuilderAgent()
        completed_sections: list[str] = []

        qual_thread = threading.Thread(
            target=self._run_qual_loop,
            args=(qual, completed_sections),
            name="qual-builder",
            daemon=True,
        )
        quant_thread = threading.Thread(
            target=self._run_quant_loop,
            args=(quant,),
            name="quant-builder",
            daemon=True,
        )

        logger.info("[session] Launching qual and quant in parallel...")
        qual_thread.start()
        quant_thread.start()
        self._run_critic_checkpoint()
        qual_thread.join()
        quant_thread.join()

        if self._qual_error:
            logger.error(f"[session] Qual builder failed: {self._qual_error}")
        if self._quant_error:
            logger.error(f"[session] Quant builder failed: {self._quant_error}")

        qual_report = qual.write_consolidated_report()
        quant_report = quant.write_consolidated_report()
        dialogue_path = self._write_dialogue_report()

        charts = quant._all_charts
        return {
            "qual_report": str(qual_report),
            "quant_report": str(quant_report),
            "dialogue_report": str(dialogue_path),
            "charts": charts,
            "messages": len(self.messenger.all_messages()),
            "unresolved_agenda_items": self.evidence.unresolved_count(),
            "critic": self._critic_result,
        }

    def _run_qual_loop(self, qual: Any, completed_sections: list[str]) -> None:
        try:
            for turn in range(1, self.max_cycles + 1):
                agenda_items = self._claim_agenda_items("qual")
                if not agenda_items:
                    if turn == 1:
                        self._qual_turn1_done.set()
                    logger.info(f"[qual] No open qual/shared agenda items at cycle {turn}; stopping")
                    break
                if self._time_exhausted():
                    if turn == 1:
                        self._qual_turn1_done.set()
                    logger.info(f"[qual] Time budget exhausted at cycle {turn}; stopping")
                    break

                clock_ctx = self.clock.prompt_context("qual_builder") if self.clock else ""
                partner_evidence_brief = self.evidence.format_cross_agent_brief("qual_builder")
                logger.info(f"[qual] Starting cycle {turn}/{self.max_cycles}")
                result = qual.run_turn(
                    turn=turn,
                    research_plan=self.research_plan,
                    messenger=self.messenger,
                    completed_sections=completed_sections,
                    agenda_items=[
                        {"id": item.id, "question": item.question, "difficulty": item.difficulty}
                        for item in agenda_items
                    ],
                    partner_evidence_brief=partner_evidence_brief,
                    clock_context=clock_ctx,
                )
                report_path = qual.write_report(turn, result["content"])
                self.evidence.ingest_payload(
                    agent_role="qual_builder",
                    payload=result.get("payload", {}),
                    report_path=report_path,
                    max_open_items=self.agenda_item_cap,
                )
                if turn == 1:
                    self._qual_turn1_done.set()
                    if self.mode != "prelim":
                        self._critic_done.wait(timeout=120)
                time.sleep(2)
        except Exception as e:
            self._qual_error = e
            logger.exception(f"[qual] Loop crashed: {e}")

    def _run_quant_loop(self, quant: Any) -> None:
        time.sleep(3)
        try:
            for turn in range(1, self.max_cycles + 1):
                agenda_items = self._claim_agenda_items("quant")
                if not agenda_items:
                    if turn == 1:
                        self._quant_turn1_done.set()
                    logger.info(f"[quant] No open quant/shared agenda items at cycle {turn}; stopping")
                    break
                if self._time_exhausted():
                    if turn == 1:
                        self._quant_turn1_done.set()
                    logger.info(f"[quant] Time budget exhausted at cycle {turn}; stopping")
                    break

                clock_ctx = self.clock.prompt_context("quant_builder") if self.clock else ""
                partner_evidence_brief = self.evidence.format_cross_agent_brief("quant_builder")
                logger.info(f"[quant] Starting cycle {turn}/{self.max_cycles}")
                result = quant.run_turn(
                    turn=turn,
                    research_plan=self.research_plan,
                    messenger=self.messenger,
                    agenda_items=[
                        {"id": item.id, "question": item.question, "difficulty": item.difficulty}
                        for item in agenda_items
                    ],
                    partner_evidence_brief=partner_evidence_brief,
                    clock_context=clock_ctx,
                )
                report_path = quant.write_report(turn, result["content"], result["charts"])
                self.evidence.ingest_payload(
                    agent_role="quant_builder",
                    payload=result.get("payload", {}),
                    report_path=report_path,
                    artifact_paths=result.get("charts", []),
                    max_open_items=self.agenda_item_cap,
                )
                if turn == 1:
                    self._quant_turn1_done.set()
                    if self.mode != "prelim":
                        self._critic_done.wait(timeout=120)
                time.sleep(2)
        except Exception as e:
            self._quant_error = e
            logger.exception(f"[quant] Loop crashed: {e}")

    def _claim_agenda_items(self, owner: str, limit: int = 3) -> list[AgendaItem]:
        with self._lock:
            items = self.evidence.open_items(owner=owner, limit=limit)
            self.evidence.claim_work_started([item.id for item in items])
            return items

    def _time_exhausted(self) -> bool:
        if not self.clock:
            return False
        return self.clock.remaining_minutes() < 3

    def _run_critic_checkpoint(self) -> None:
        if self.mode == "prelim":
            self._critic_done.set()
            return

        while True:
            if self._qual_error or self._quant_error:
                self._critic_done.set()
                return
            if self._qual_turn1_done.is_set() and self._quant_turn1_done.is_set():
                break
            time.sleep(0.5)

        try:
            from agentorg.agents.critic import CriticAgent

            logger.info("[session] Running critic checkpoint after turn 1")
            self._critic_result = CriticAgent(
                evidence=self.evidence,
                research_plan=self.research_plan,
            ).run(dry_run=False)
        except Exception as e:
            logger.exception(f"[session] Critic checkpoint failed: {e}")
            self._critic_result = {"status": "failed", "error": str(e)}
        finally:
            self._critic_done.set()

    def _write_dialogue_report(self) -> Path:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = config.REPORTS_DIR / f"{timestamp}_session_dialogue.md"
        content = (
            "# Qual ↔ Quant Research Dialogue\n\n"
            "*Auto-generated cross-agent conversation log*\n\n"
            "---\n\n"
            f"{self.messenger.format_full_dialogue()}"
        )
        path.write_text(content, encoding="utf-8")
        logger.info(f"[session] Dialogue log → {path.name}")
        return path


def run_collaborative_session(
    research_plan: str,
    agenda_seed: list[str],
    time_budget: str = "",
    max_cycles: int | None = None,
    mode: str = "deep",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Run the collaborative session only; orchestration of verify/report happens above this layer."""
    import os
    from agentorg.timing import parse_budget_string

    if time_budget:
        os.environ["TIME_BUDGET"] = time_budget
        config.TIME_BUDGET = time_budget

    # Always initialize a fresh clock — never load a stale one from a prior run.
    # RunClock.load() would pick up an old .run_meta.json committed to the repo
    # and report zero remaining time, causing agents to bail immediately.
    clock = RunClock.initialize(parse_budget_string(time_budget)) if time_budget else None

    if dry_run:
        logger.info("[session] Dry-run mode — skipping agent calls")
        return {"status": "dry_run"}

    session = CollaborativeSession(
        research_plan=research_plan,
        agenda_seed=agenda_seed,
        clock=clock,
        max_cycles=max_cycles,
        mode=mode,
    )
    return session.run()
