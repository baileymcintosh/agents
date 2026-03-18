"""
Project manager for per-project working directories and optional GitHub repos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

try:
    from loguru import logger
except ImportError:  # pragma: no cover - minimal test environment fallback
    import logging

    logger = logging.getLogger(__name__)


GITHUB_USER = os.getenv("GITHUB_USER", "baileymcintosh")
GH_CLI = os.getenv("GH_CLI", shutil.which("gh") or "gh")
PROJECTS_ROOT = Path(
    os.getenv(
        "AGENTORG_PROJECTS_ROOT",
        str(Path.home() / "OneDrive - PennO365" / "Projects" / "GITHUB" / "agent projects"),
    )
)


def create_project(project_name: str, brief: str, plan_content: str = "") -> dict:
    """Create local directory structure and, if enabled, a GitHub repo."""
    project_dir = PROJECTS_ROOT / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    for subdir in ["reports", "data", "notebooks"]:
        (project_dir / subdir).mkdir(exist_ok=True)

    (project_dir / "BRIEF.md").write_text(f"# Brief\n\n{brief}\n", encoding="utf-8")
    if plan_content:
        (project_dir / "PLAN.md").write_text(plan_content, encoding="utf-8")

    feedback_path = project_dir / "FEEDBACK.md"
    if not feedback_path.exists():
        feedback_path.write_text(
            "# Feedback\n\nAdd your feedback here after reviewing the preliminary outputs.\n",
            encoding="utf-8",
        )

    _run(["git", "init"], cwd=project_dir)
    _run(["git", "add", "."], cwd=project_dir)
    try:
        _run(["git", "commit", "-m", "init: project setup"], cwd=project_dir)
    except subprocess.CalledProcessError:
        logger.info("[project_manager] Initial commit skipped (nothing to commit)")

    github_url = _create_github_repo(project_name, brief, project_dir)
    logger.info(f"[project_manager] Project ready: {project_dir}")
    return {"project_dir": str(project_dir), "github_url": github_url}


def push(project_dir: Path, message: str = "chore: update") -> None:
    """Stage all changes and push to GitHub when a remote exists."""
    _run(["git", "add", "-A"], cwd=project_dir)
    result = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=project_dir, capture_output=True)
    if result.returncode != 0:
        _run(["git", "commit", "-m", message], cwd=project_dir)

    remotes = subprocess.run(["git", "remote"], cwd=project_dir, capture_output=True, text=True, check=False)
    if "origin" not in remotes.stdout.split():
        logger.info(f"[project_manager] No git remote configured for {project_dir.name}; push skipped")
        return
    # Check whether origin/main exists (empty repo has no branches yet)
    ls_remote = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", "main"],
        cwd=project_dir, capture_output=True, text=True, check=False,
    )
    if ls_remote.stdout.strip():
        _run(["git", "pull", "--rebase", "origin", "main"], cwd=project_dir)
    _run(["git", "push", "--set-upstream", "origin", "main"], cwd=project_dir)
    logger.info(f"[project_manager] Pushed -> {project_dir.name}")


def _create_github_repo(project_name: str, description: str, project_dir: Path) -> str:
    """Create and push a public GitHub repo unless disabled."""
    if os.getenv("AGENTORG_CREATE_GITHUB_REPO", "true").lower() != "true":
        logger.info("[project_manager] GitHub repo creation disabled by env")
        return ""
    if not shutil.which(str(GH_CLI)) and GH_CLI == "gh":
        logger.warning("[project_manager] gh CLI not found on PATH; skipping repo creation")
        return ""

    short_desc = description[:100].replace('"', "'").split("\n")[0]
    try:
        result = subprocess.run(
            [
                GH_CLI,
                "repo",
                "create",
                f"{GITHUB_USER}/{project_name}",
                "--public",
                "--description",
                short_desc,
                "--source",
                str(project_dir),
                "--remote",
                "origin",
                "--push",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if result.returncode == 0:
            url = f"https://github.com/{GITHUB_USER}/{project_name}"
            logger.info(f"[project_manager] GitHub repo created: {url}")
            return url
        logger.warning(f"[project_manager] gh repo create failed: {result.stderr}")
        return ""
    except Exception as e:
        logger.warning(f"[project_manager] Could not create GitHub repo: {e}")
        return ""


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)
