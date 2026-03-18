"""Canonical project runner: planner output -> collaborative session -> verifier -> reporter."""

from __future__ import annotations

import contextlib
import datetime
from pathlib import Path
from typing import Any, Iterator

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)

from agentorg import config, session_state
from agentorg.approval import create as create_publication_approval
from agentorg.agents.qa_editor import QAEditorAgent
from agentorg.agents.reporter import ReporterAgent
from agentorg.agents.session import run_collaborative_session
from agentorg.agents.verifier import VerifierAgent
from agentorg.memory import (
    build_memory_context,
    load_relevant_memories,
    memory_seed_questions,
    source_registry_guidance,
    update_source_registry,
    write_project_memory,
)


PRELIM_MODEL_OVERRIDES: dict[str, Any] = {
    "QUAL_BUILDER_MODEL": config.PRELIM_MODEL,
    "VERIFIER_MODEL": config.PRELIM_MODEL,
    "FAST_MODE": True,
}


def run_prelim(session: session_state.ProjectSession) -> dict[str, Any]:
    return _run_project_cycle(session, mode="prelim")


def run_deep(session: session_state.ProjectSession, feedback: str = "") -> dict[str, Any]:
    return _run_project_cycle(session, mode="deep", feedback=feedback)


def _run_project_cycle(
    session: session_state.ProjectSession,
    mode: str,
    feedback: str = "",
) -> dict[str, Any]:
    project_dir = Path(session.project_dir)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    brief_path = project_dir / "BRIEF.md"
    plan_path = project_dir / "PLAN.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else session.brief
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    goals = _extract_goals(plan_text, mode)
    time_budget = "8m" if mode == "prelim" else (config.TIME_BUDGET or "60m")
    max_cycles = 2 if mode == "prelim" else max(config.SESSION_COLLAB_TURNS, 6)
    related_memories = load_relevant_memories(
        project_dir=project_dir,
        project_name=session.name,
        brief=brief,
        limit=config.MEMORY_RETRIEVAL_LIMIT,
    )
    agenda_seed = goals or ["Produce a defensible synthesis with claims, sources, and charts."]
    seeded_questions = memory_seed_questions(related_memories)
    existing_questions = {question.strip().lower() for question in agenda_seed}
    for question in seeded_questions:
        key = question.strip().lower()
        if key not in existing_questions:
            agenda_seed.append(question)
            existing_questions.add(key)

    research_plan = _compose_research_plan(
        project_name=session.name,
        brief=brief,
        plan_text=plan_text,
        goals=agenda_seed,
        mode=mode,
        feedback=feedback,
        memory_context=build_memory_context(related_memories),
        source_guidance=source_registry_guidance(project_dir, related_memories),
    )

    with _project_runtime(project_dir=project_dir, reports_dir=reports_dir, mode=mode, time_budget=time_budget):
        start = datetime.datetime.now()
        logger.info(f"[runner] Starting canonical {mode} cycle for '{session.name}'")
        session_result = run_collaborative_session(
            research_plan=research_plan,
            agenda_seed=agenda_seed,
            time_budget=time_budget,
            max_cycles=max_cycles,
            mode=mode,
            dry_run=False,
        )

        verifier = VerifierAgent()
        verifier_result = verifier.run(dry_run=False)
        outputs = [
            session_result.get("qual_report"),
            session_result.get("quant_report"),
            session_result.get("dialogue_report"),
            verifier_result.get("report"),
        ]

        reporter_result: dict[str, Any] | None = None
        qa_result: dict[str, Any] | None = None
        approval_result = None
        if verifier_result.get("verdict") == "PASS":
            reporter_result = ReporterAgent().run(dry_run=False)
            qa_result = QAEditorAgent(brief=brief, research_plan=research_plan).run(
                report_path=reporter_result.get("report", ""),
                dry_run=False,
            )
            if qa_result.get("verdict") == "REVISE":
                logger.info("[runner] QA editor requested revision; running reporter once more")
                reporter_result = ReporterAgent().run(
                    dry_run=False,
                    revision_instructions=qa_result.get("instructions", ""),
                )

            final_outputs = [
                session_result.get("qual_report"),
                session_result.get("quant_report"),
                session_result.get("dialogue_report"),
                verifier_result.get("report"),
                reporter_result.get("report"),
                reporter_result.get("notebook"),
                reporter_result.get("pdf"),
                qa_result.get("report") if qa_result else None,
            ]

            requires_approval = bool(config.PUBLICATION_APPROVAL_REQUIRED) and mode == "deep"
            approval_summary = (
                f"{mode.title()} run for {session.name} passed verification "
                f"with {len(session_result.get('charts', []))} chart(s) and "
                f"{session_result.get('messages', 0)} collaboration message(s)."
            )
            approval_result = create_publication_approval(
                reports_dir,
                run_id=f"{session.name}-{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
                project_name=session.name,
                project_dir=str(project_dir),
                mode=mode,
                requires_approval=requires_approval,
                verifier_verdict=verifier_result.get("verdict", ""),
                report_path=reporter_result.get("report", ""),
                notebook_path=reporter_result.get("notebook", ""),
                pdf_path=reporter_result.get("pdf", ""),
                qa_report_path=qa_result.get("report", "") if qa_result else "",
                outputs=[output for output in final_outputs if output],
                summary=approval_summary,
            )
            session.publication_approval_required = approval_result.requires_approval
            session.publication_approval_status = approval_result.status
            session.publication_approval_run_id = approval_result.run_id
            session.publication_approval_path = str(reports_dir / "_state" / "publication_approval.json")
            session.publication_approval_updated_at = approval_result.updated_at
            outputs = [output for output in final_outputs if output]
        else:
            logger.warning(
                f"[runner] Reporter skipped because verifier verdict was {verifier_result.get('verdict')}"
            )
        memory_path = write_project_memory(
            project_dir=project_dir,
            project_name=session.name,
            brief=brief,
            store=verifier.store,
        )
        registry_path = update_source_registry(project_dir=project_dir, store=verifier.store)
        outputs.extend([str(memory_path), str(registry_path)])
        if approval_result and approval_result.is_pending():
            logger.info("[runner] Publication approval required; skipping auto-push")
        else:
            _push(project_dir, f"{mode}: collaborative research cycle")
        elapsed = int((datetime.datetime.now() - start).total_seconds())

    return {
        "outputs": [output for output in outputs if output],
        "session": session_result,
        "verification": verifier_result,
        "reporter": reporter_result,
        "qa_editor": qa_result if verifier_result.get("verdict") == "PASS" else None,
        "approval": approval_result.to_dict() if approval_result else None,
        "mode": mode,
        "elapsed_seconds": elapsed,
    }


def _extract_goals(plan_text: str, mode: str) -> list[str]:
    section_name = "Preliminary Run Goals" if mode == "prelim" else "Deep Research Goals"
    goals: list[str] = []
    in_section = False
    for line in plan_text.splitlines():
        if section_name in line:
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.strip().startswith("- "):
            goals.append(line.strip()[2:])
    return goals


def _compose_research_plan(
    project_name: str,
    brief: str,
    plan_text: str,
    goals: list[str],
    mode: str,
    feedback: str,
    memory_context: str = "",
    source_guidance: str = "",
) -> str:
    goals_block = "\n".join(f"- {goal}" for goal in goals) or "- Produce the highest-value missing research."
    plan_parts = [
        f"# {mode.title()} Research Cycle",
        "",
        f"## Project\n{project_name}",
        "",
        "## Brief",
        brief,
        "",
        "## Agenda Goals",
        goals_block,
    ]
    if plan_text:
        plan_parts.extend(["", "## Team Planner Plan", plan_text])
    if memory_context:
        plan_parts.extend(["", memory_context])
    if source_guidance:
        plan_parts.extend(["", source_guidance])
    if feedback:
        plan_parts.extend(["", "## Feedback", feedback])
    return "\n".join(plan_parts)


@contextlib.contextmanager
def _project_runtime(
    project_dir: Path,
    reports_dir: Path,
    mode: str,
    time_budget: str,
) -> Iterator[None]:
    previous = {
        "REPORTS_DIR": config.REPORTS_DIR,
        "FAST_MODE": config.FAST_MODE,
        "TIME_BUDGET": config.TIME_BUDGET,
        "QUAL_BUILDER_MODEL": config.QUAL_BUILDER_MODEL,
        "VERIFIER_MODEL": config.VERIFIER_MODEL,
    }
    config.set_reports_dir(reports_dir)
    config.TIME_BUDGET = time_budget
    if mode == "prelim":
        config.QUAL_BUILDER_MODEL = PRELIM_MODEL_OVERRIDES["QUAL_BUILDER_MODEL"]
        config.VERIFIER_MODEL = PRELIM_MODEL_OVERRIDES["VERIFIER_MODEL"]
        config.FAST_MODE = PRELIM_MODEL_OVERRIDES["FAST_MODE"]
    else:
        config.FAST_MODE = False

    # Clear evidence state so each run starts with a clean slate.
    # Without this, claims/sources from prior runs accumulate and cause false
    # verifier FAILs on the next run (e.g., old claims with no artifact_paths
    # polluting the new run's quant provenance check).
    _clear_evidence_state(reports_dir)

    try:
        yield
    finally:
        config.set_reports_dir(previous["REPORTS_DIR"])
        config.FAST_MODE = previous["FAST_MODE"]
        config.TIME_BUDGET = previous["TIME_BUDGET"]
        config.QUAL_BUILDER_MODEL = previous["QUAL_BUILDER_MODEL"]
        config.VERIFIER_MODEL = previous["VERIFIER_MODEL"]


def _clear_evidence_state(reports_dir: Path) -> None:
    """Remove per-run evidence state files so each run starts clean."""
    state_dir = reports_dir / "_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    _EPHEMERAL_STATE = ("claims.json", "sources.json", "agenda.json", "verification.json")
    for fname in _EPHEMERAL_STATE:
        path = state_dir / fname
        if path.exists():
            path.unlink()
            logger.info(f"[runner] Cleared stale state: {fname}")


def _push(project_dir: Path, message: str) -> None:
    try:
        from agentorg.project_manager import push

        push(project_dir, message)
    except Exception as e:
        logger.warning(f"[runner] Push failed (non-fatal): {e}")
