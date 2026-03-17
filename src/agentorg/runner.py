"""
Runner — executes agent teams locally with streaming output.

Two modes:
  prelim  — fast, cheap models (Groq/DeepSeek), 3 goals, target <10 min
  deep    — full models, all goals, no time cap (or explicit budget)

Outputs land in the project directory. Runner writes a RUN_LOG.md
so we always know what happened.
"""

from __future__ import annotations

import datetime
import importlib
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from loguru import logger

from agentorg import config, session_state


# Model overrides for prelim runs — cheap and fast
PRELIM_MODEL_OVERRIDES: dict[str, str] = {
    "researcher": config.PRELIM_MODEL,        # Groq Llama
    "qual_builder": config.PRELIM_MODEL,      # Groq Llama
    "data_analyst": "deepseek-chat",          # DeepSeek V3 — good at code/data
    "quant_builder": "deepseek-chat",
    "coder": "deepseek-chat",
    "verifier": config.PRELIM_MODEL,
    # planner + debugger always use their configured (expensive) model
    # reporter uses Sonnet even in prelim for quality synthesis
    "reporter": "claude-sonnet-4-6",
}


def run_prelim(session: session_state.ProjectSession) -> dict[str, Any]:
    """
    Run the team in preliminary mode: cheap models, limited goals, <10 min target.
    Returns dict with output paths and summary.
    """
    project_dir = Path(session.project_dir)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Override env vars for cheap models
    env = {**os.environ}
    for role, model in PRELIM_MODEL_OVERRIDES.items():
        env_key = f"{role.upper()}_MODEL"
        env[env_key] = model
    env["REPORTS_DIR"] = str(reports_dir)
    env["FAST_MODE"] = "false"
    env["TIME_BUDGET"] = "8m"  # hard cap for prelim

    # Build the prelim prompt from session goals
    goals_text = "\n".join(f"- {g}" for g in _get_prelim_goals(session))
    brief_path = project_dir / "BRIEF.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else session.brief

    prelim_brief = f"""PRELIMINARY RUN — validate data sources and produce quick first-pass outputs.

Project: {session.name}
Brief: {brief}

Goals for this run (complete as many as possible in <10 min):
{goals_text}

Keep outputs concise. Focus on proving you can access the right data and
produce sensible preliminary findings. This is a validation run, not the final product.
"""

    # Write prelim brief to project dir so agents can read it
    (project_dir / "PRELIM_BRIEF.md").write_text(prelim_brief, encoding="utf-8")

    logger.info(f"[runner] Starting prelim run for '{session.name}'")
    start = datetime.datetime.now()
    outputs: list[str] = []

    for role in session.team:
        if role == "reporter":
            continue  # run reporter last
        output = _run_agent(role, env, project_dir, mode="prelim")
        if output:
            outputs.append(output)

    # Run reporter to synthesise
    output = _run_agent("reporter", env, project_dir, mode="prelim")
    if output:
        outputs.append(output)

    elapsed = (datetime.datetime.now() - start).seconds
    logger.info(f"[runner] Prelim run complete in {elapsed}s")

    # Push to GitHub
    _push(project_dir, f"prelim: initial outputs ({elapsed}s)")

    return {
        "outputs": outputs,
        "elapsed_seconds": elapsed,
        "reports_dir": str(reports_dir),
    }


def run_deep(session: session_state.ProjectSession, feedback: str = "") -> dict[str, Any]:
    """
    Run the team in deep mode: full models, all goals.
    """
    project_dir = Path(session.project_dir)
    reports_dir = project_dir / "reports"
    reports_dir.mkdir(exist_ok=True)

    env = {**os.environ}
    env["REPORTS_DIR"] = str(reports_dir)
    env["FAST_MODE"] = "false"

    brief_path = project_dir / "BRIEF.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else session.brief

    deep_prompt = f"""DEEP RESEARCH RUN

Project: {session.name}
Brief: {brief}
"""
    if feedback:
        deep_prompt += f"\nFeedback from preliminary run:\n{feedback}\n"

    (project_dir / "DEEP_BRIEF.md").write_text(deep_prompt, encoding="utf-8")

    logger.info(f"[runner] Starting deep run for '{session.name}'")
    start = datetime.datetime.now()
    outputs: list[str] = []

    # Run parallel agents (qual + quant) if both in team
    parallel_roles = [r for r in session.team if r in ("qual_builder", "quant_builder", "researcher", "data_analyst")]
    sequential_roles = [r for r in session.team if r not in parallel_roles + ["reporter"]]

    if len(parallel_roles) >= 2:
        outputs.extend(_run_parallel(parallel_roles, env, project_dir))
    else:
        for role in parallel_roles:
            out = _run_agent(role, env, project_dir, mode="deep")
            if out:
                outputs.append(out)

    for role in sequential_roles:
        out = _run_agent(role, env, project_dir, mode="deep")
        if out:
            outputs.append(out)

    out = _run_agent("reporter", env, project_dir, mode="deep")
    if out:
        outputs.append(out)

    elapsed = (datetime.datetime.now() - start).seconds
    _push(project_dir, f"deep: research outputs ({elapsed // 60}m)")

    return {"outputs": outputs, "elapsed_seconds": elapsed}


def _run_agent(role: str, env: dict, project_dir: Path, mode: str) -> str | None:
    """Run a single agent as a subprocess, streaming output. Returns report path or None."""
    cmd = [sys.executable, "-m", "agentorg.cli", "run", role]
    log_file = project_dir / "reports" / f"run_{role}_{mode}.log"

    logger.info(f"[runner] → {role} ({mode})")
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            result = subprocess.run(
                cmd,
                env={**env, "PYTHONPATH": str(Path(__file__).parent.parent)},
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=600,  # 10 min hard cap per agent
                cwd=str(project_dir),
            )
        if result.returncode != 0:
            logger.warning(f"[runner] {role} exited with code {result.returncode}")
        return str(log_file)
    except subprocess.TimeoutExpired:
        logger.warning(f"[runner] {role} timed out after 10 min")
        return None
    except Exception as e:
        logger.warning(f"[runner] {role} failed: {e}")
        return None


def _run_parallel(roles: list[str], env: dict, project_dir: Path) -> list[str]:
    """Run multiple agents in parallel threads. Returns list of output paths."""
    results: dict[str, str | None] = {}

    def _target(role: str) -> None:
        results[role] = _run_agent(role, env, project_dir, mode="deep")

    threads = [threading.Thread(target=_target, args=(r,)) for r in roles]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return [v for v in results.values() if v]


def _push(project_dir: Path, message: str) -> None:
    try:
        from agentorg.project_manager import push
        push(project_dir, message)
    except Exception as e:
        logger.warning(f"[runner] Push failed (non-fatal): {e}")


def _get_prelim_goals(session: session_state.ProjectSession) -> list[str]:
    """Extract prelim goals from plan file or fall back to generic."""
    plan_path = Path(session.project_dir) / "PLAN.md"
    if plan_path.exists():
        text = plan_path.read_text(encoding="utf-8")
        # Extract bullet points under "Preliminary Run Goals"
        in_section = False
        goals = []
        for line in text.splitlines():
            if "Preliminary Run Goals" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("## "):
                    break
                if line.strip().startswith("- "):
                    goals.append(line.strip()[2:])
        if goals:
            return goals
    return [
        "Identify and validate key data sources",
        "Produce initial summary of the topic",
        "Generate at least one data chart or table",
    ]
