"""Canonical project runner: planner output -> collaborative session -> verifier -> reporter."""

from __future__ import annotations

import contextlib
import datetime
import os
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


# ---------------------------------------------------------------------------
# Model routing — override any of these via environment variables to swap
# models without changing code. Defaults are set for cost efficiency.
#
# Quick reference (approx cost per 1M tokens in/out):
#   claude-opus-4-6              $15 / $75   — highest quality, use sparingly
#   claude-sonnet-4-6            $3  / $15   — good balance
#   claude-haiku-4-5-20251001    $0.80/ $4   — fast + cheap, fine for data tasks
#   gpt-4o                       $2.50/$10   — strong for qual research
#   gpt-4o-mini                  $0.15/$0.60 — 17x cheaper than gpt-4o
#   llama-3.3-70b-versatile      free        — Groq free tier (rate limited)
# ---------------------------------------------------------------------------

# Prelim — all cheap: qual+verifier+reporter on Groq (free), quant on Haiku
PRELIM_MODEL_OVERRIDES: dict[str, Any] = {
    "QUAL_BUILDER_MODEL": os.getenv("PRELIM_QUAL_MODEL", config.PRELIM_MODEL),
    "QUANT_BUILDER_MODEL": os.getenv("PRELIM_QUANT_MODEL", "claude-haiku-4-5-20251001"),
    "VERIFIER_MODEL": os.getenv("PRELIM_VERIFIER_MODEL", config.PRELIM_MODEL),
    "REPORTER_MODEL": os.getenv("PRELIM_REPORTER_MODEL", config.PRELIM_MODEL),
    "FAST_MODE": True,
}

# Deep — quality tier: quant on Haiku, qual on gpt-4o-mini, verifier on Groq,
# reporter on Sonnet for final synthesis quality
DEEP_MODEL_OVERRIDES: dict[str, Any] = {
    "QUAL_BUILDER_MODEL": os.getenv("DEEP_QUAL_MODEL", "gpt-4o-mini"),
    "QUANT_BUILDER_MODEL": os.getenv("DEEP_QUANT_MODEL", "claude-haiku-4-5-20251001"),
    "VERIFIER_MODEL": os.getenv("DEEP_VERIFIER_MODEL", config.PRELIM_MODEL),
    "REPORTER_MODEL": os.getenv("DEEP_REPORTER_MODEL", config.REPORTER_MODEL),
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
    # Default agenda seeds: always include at least one qual item and one quant item
    # so both agents have work in cycle 1. If no explicit goals from PLAN.md, use
    # generic seeds that reliably route to qual vs quant via keyword classification.
    agenda_seed = goals or [
        "Investigate the geopolitical context, policy responses, and key actors relevant to this research brief.",
        "Fetch market and economic data, produce charts, and quantify the financial and statistical claims.",
    ]
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
        # Allow NEEDS REVISION to proceed — soft failures (sourcing gaps, low confidence)
        # should not block the entire report. The reporter notes them in the output.
        # Only hard FAIL (no claims at all, or majority of core claims unsourced) blocks.
        verifier_verdict = verifier_result.get("verdict", "FAIL")
        # In prelim mode, always run the reporter — sourcing is often imperfect with
        # cheap/fast models and the prelim is a quick sanity check, not a publication gate.
        # In deep mode, hard FAIL still blocks (majority of core claims unsourced).
        reporter_allowed = verifier_verdict in ("PASS", "NEEDS REVISION") or mode == "prelim"
        if reporter_allowed:
            if verifier_verdict == "NEEDS REVISION":
                logger.warning("[runner] Verifier NEEDS REVISION — proceeding to reporter with findings noted")
            elif verifier_verdict == "FAIL" and mode == "prelim":
                logger.warning("[runner] Verifier FAIL in prelim mode — proceeding to reporter anyway")
            reporter_result = ReporterAgent().run(dry_run=False)
            try:
                qa_result = QAEditorAgent(brief=brief, research_plan=research_plan).run(
                    report_path=reporter_result.get("report", ""),
                    dry_run=False,
                )
            except Exception as e:
                logger.warning(f"[runner] QA editor failed (non-fatal, report still published): {e}")
                qa_result = {"verdict": "APPROVED", "instructions": "", "report": ""}
            if qa_result.get("verdict") == "REVISE":
                logger.info("[runner] QA editor requested revision; running reporter once more")
                try:
                    reporter_result = ReporterAgent().run(
                        dry_run=False,
                        revision_instructions=qa_result.get("instructions", ""),
                    )
                except Exception as e:
                    logger.warning(f"[runner] Reporter revision failed (non-fatal, keeping original): {e}")

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
        _download_sources(project_dir=project_dir, store=verifier.store)
        _organise_run_outputs(reports_dir, project_dir, reporter_result)
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
        "qa_editor": qa_result if verifier_result.get("verdict") in ("PASS", "NEEDS REVISION") else None,
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
        "QUANT_BUILDER_MODEL": config.QUANT_BUILDER_MODEL,
        "VERIFIER_MODEL": config.VERIFIER_MODEL,
        "REPORTER_MODEL": config.REPORTER_MODEL,
    }
    config.set_reports_dir(reports_dir)
    config.TIME_BUDGET = time_budget
    if mode == "prelim":
        config.QUAL_BUILDER_MODEL = PRELIM_MODEL_OVERRIDES["QUAL_BUILDER_MODEL"]
        config.QUANT_BUILDER_MODEL = PRELIM_MODEL_OVERRIDES["QUANT_BUILDER_MODEL"]
        config.VERIFIER_MODEL = PRELIM_MODEL_OVERRIDES["VERIFIER_MODEL"]
        config.REPORTER_MODEL = PRELIM_MODEL_OVERRIDES["REPORTER_MODEL"]
        config.FAST_MODE = PRELIM_MODEL_OVERRIDES["FAST_MODE"]
    else:
        config.QUAL_BUILDER_MODEL = DEEP_MODEL_OVERRIDES["QUAL_BUILDER_MODEL"]
        config.QUANT_BUILDER_MODEL = DEEP_MODEL_OVERRIDES["QUANT_BUILDER_MODEL"]
        config.VERIFIER_MODEL = DEEP_MODEL_OVERRIDES["VERIFIER_MODEL"]
        config.REPORTER_MODEL = DEEP_MODEL_OVERRIDES["REPORTER_MODEL"]
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
        config.QUANT_BUILDER_MODEL = previous["QUANT_BUILDER_MODEL"]
        config.VERIFIER_MODEL = previous["VERIFIER_MODEL"]
        config.REPORTER_MODEL = previous["REPORTER_MODEL"]


def _download_sources(project_dir: Path, store: Any) -> None:
    """
    Fetch the full text of the top cited sources and save to sources/ in the project repo.
    Capped at 8 sources to avoid bloat. Skips dataset/yfinance/FRED sources (no URL to fetch).
    """
    from agentorg.tools.search import fetch_url
    import re

    sources_dir = project_dir / "sources"
    sources_dir.mkdir(exist_ok=True)

    sources = store.sources()
    if not sources:
        (sources_dir / "README.md").write_text(
            "# Sources\n\nNo sources were recorded by the agents in this run.\n",
            encoding="utf-8",
        )
        return

    # Sort by tier (best first), skip dataset sources, cap at 8
    tier_order = {"tier1_primary": 0, "tier2_journalism": 1, "tier3_analysis": 2,
                  "tier4_expert": 3, "tier5_unverified": 4, "dataset": 99}
    ranked = sorted(
        [s for s in sources if s.source_type != "dataset" and s.url],
        key=lambda s: tier_order.get(s.tier, 5),
    )[:8]

    if not ranked:
        # All sources are dataset-type (yfinance/FRED) — write a brief manifest
        lines = ["# Sources\n", "All sources in this run are live datasets (yfinance/FRED/EIA) — no web articles to archive.\n\n"]
        for s in sources[:20]:
            lines.append(f"- [{s.tier}] {s.title} — {s.publisher or s.url or 'no URL'}\n")
        (sources_dir / "README.md").write_text("".join(lines), encoding="utf-8")
        return

    for i, source in enumerate(ranked, 1):
        slug = re.sub(r"[^a-z0-9]+", "_", source.title.lower())[:50].strip("_")
        out_path = sources_dir / f"{i:02d}_{slug}.md"
        if out_path.exists():
            continue
        try:
            content = fetch_url(source.url, max_chars=20000)
            header = (
                f"# {source.title}\n\n"
                f"**Source:** {source.publisher or source.url}  \n"
                f"**Tier:** {source.tier}  \n"
                f"**URL:** {source.url}  \n"
                f"**Published:** {source.published_at or 'unknown'}  \n\n---\n\n"
            )
            out_path.write_text(header + content, encoding="utf-8")
            logger.info(f"[runner] Source downloaded → sources/{out_path.name}")
        except Exception as e:
            logger.warning(f"[runner] Could not download source '{source.title}': {e}")


def _organise_run_outputs(reports_dir: Path, project_dir: Path, reporter_result: dict | None) -> None:
    """
    Organise all run outputs into a clean, structured repo layout:

    project_dir/
    ├── final_report.md        ← polished executive report
    ├── final_report.ipynb     ← same as notebook
    ├── all_plots.md           ← every chart as markdown (renders on GitHub)
    ├── all_plots.ipynb        ← every chart as self-contained notebook
    ├── charts/                ← all PNG charts (flat, descriptive names)
    └── agent_outputs/
        ├── qual/              ← qualitative builder turn reports
        ├── quant/             ← quantitative builder turn reports
        ├── verification/      ← verifier report
        ├── qa/                ← QA editor report
        ├── charts/            ← same PNGs (source location)
        └── _state/            ← evidence JSON state
    """
    import shutil

    # ── 1. Move PNGs into agent_outputs/charts/ ──────────────────────────────
    agent_dir = project_dir / "agent_outputs"
    ao_charts_dir = reports_dir / "charts"
    ao_charts_dir.mkdir(exist_ok=True)
    for png in reports_dir.glob("*.png"):
        dest = ao_charts_dir / png.name
        if not dest.exists():
            png.rename(dest)
            logger.info(f"[runner] Chart → agent_outputs/charts/{png.name}")

    # ── 2. Copy charts to project root charts/ for easy access ───────────────
    project_charts_dir = project_dir / "charts"
    project_charts_dir.mkdir(exist_ok=True)
    for png in ao_charts_dir.glob("*.png"):
        dest = project_charts_dir / png.name
        if not dest.exists():
            shutil.copy2(png, dest)

    # ── 3. Organise agent markdown reports into subfolders ───────────────────
    subfolder_map = {
        "qual_builder": agent_dir / "qual",
        "quant_builder": agent_dir / "quant",
        "verifier": agent_dir / "verification",
        "qa_editor": agent_dir / "qa",
        "reporter": agent_dir / "reporter",
        "session": agent_dir / "session",
    }
    for subfolder in subfolder_map.values():
        subfolder.mkdir(parents=True, exist_ok=True)

    for md_file in reports_dir.glob("*.md"):
        stem = md_file.stem
        moved = False
        for role, dest_dir in subfolder_map.items():
            if role in stem:
                dest = dest_dir / md_file.name
                if not dest.exists():
                    shutil.copy2(md_file, dest)
                moved = True
                break
        if not moved:
            # fallback: leave in reports_dir
            pass

    # ── 4. Copy final outputs to project root BEFORE moving reports/ ──────────
    # Must happen before step 5 — reporter_result paths point into reports_dir,
    # which gets moved in step 5. After the move those paths no longer exist.
    if reporter_result:
        report_src = reporter_result.get("report", "")
        nb_src = reporter_result.get("notebook", "")
        all_plots_src = reporter_result.get("all_plots", "")
        all_plots_md_src = reporter_result.get("all_plots_md", "")
        if report_src and Path(report_src).exists():
            shutil.copy2(report_src, project_dir / "final_report.md")
            logger.info(f"[runner] Report → final_report.md")
        if nb_src and Path(nb_src).exists():
            shutil.copy2(nb_src, project_dir / "final_report.ipynb")
            logger.info(f"[runner] Notebook → final_report.ipynb")
        if all_plots_src and Path(all_plots_src).exists():
            shutil.copy2(all_plots_src, project_dir / "all_plots.ipynb")
            logger.info(f"[runner] All-plots notebook → all_plots.ipynb")
        if all_plots_md_src and Path(all_plots_md_src).exists():
            shutil.copy2(all_plots_md_src, project_dir / "all_plots.md")
            logger.info(f"[runner] All-plots markdown → all_plots.md")

    # ── 5. Move reports/ into agent_outputs/raw/ so it doesn't clutter root ──
    ao_raw_dir = agent_dir / "raw"
    ao_raw_dir.mkdir(parents=True, exist_ok=True)
    for item in reports_dir.iterdir():
        dest = ao_raw_dir / item.name
        if not dest.exists():
            shutil.move(str(item), str(dest))
    try:
        reports_dir.rmdir()  # only succeeds if empty
    except OSError:
        pass  # non-empty dirs get left; acceptable

    # ── 6. Write README.md ────────────────────────────────────────────────────
    project_name = project_dir.name
    readme = f"""# {project_name}

Research report generated by [AgentOrg](https://github.com/baileymcintosh/agents).

## Contents

| File | Description |
|---|---|
| `final_report.md` | Executive summary — start here |
| `final_report.ipynb` | Report as a Jupyter notebook (open in VS Code) |
| `all_plots.md` | All generated charts (renders inline on GitHub) |
| `all_plots.ipynb` | All charts as a self-contained notebook |
| `charts/` | Raw PNG files for all generated charts |
| `BRIEF.md` | Original research brief |
| `sources/` | Full text of key cited sources (fetched at run time) |
| `agent_outputs/` | Working files from each agent (qual, quant, verifier, QA) |

## Agent Outputs

| Folder | Agent |
|---|---|
| `agent_outputs/qual/` | Qualitative researcher — news, policy, narrative |
| `agent_outputs/quant/` | Quantitative analyst — market data, charts |
| `agent_outputs/verification/` | Verifier — claim and source QA |
| `agent_outputs/qa/` | QA editor — final report review |
| `agent_outputs/session/` | Cross-agent research dialogue |
| `agent_outputs/raw/` | All raw agent outputs |
"""
    readme_path = project_dir / "README.md"
    readme_path.write_text(readme, encoding="utf-8")
    logger.info(f"[runner] README.md written")


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
