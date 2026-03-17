"""
ProjectManager — creates local project directories and GitHub repos.

Each project gets:
  ~/OneDrive - PennO365/Projects/GITHUB/<project-name>/
    BRIEF.md          — original task brief
    PLAN.md           — team plan (written before prelim run)
    FEEDBACK.md       — Bailey's feedback between runs (edited by hand or by me)
    reports/          — all agent outputs land here
    data/             — raw data files
    notebooks/        — Jupyter notebooks

And a public GitHub repo: baileymcintosh/<project-name>
"""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from loguru import logger


GITHUB_USER = "baileymcintosh"
GH_CLI = "/c/Program Files/GitHub CLI/gh.exe"
PROJECTS_ROOT = Path.home() / "OneDrive - PennO365" / "Projects" / "GITHUB"


def create_project(project_name: str, brief: str, plan_content: str = "") -> dict:
    """
    Create local directory structure + GitHub repo.
    Returns dict with project_dir and github_url.
    """
    project_dir = PROJECTS_ROOT / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    # Subdirectories
    for subdir in ["reports", "data", "notebooks"]:
        (project_dir / subdir).mkdir(exist_ok=True)

    # Write brief
    (project_dir / "BRIEF.md").write_text(f"# Brief\n\n{brief}\n", encoding="utf-8")

    # Write plan if provided
    if plan_content:
        (project_dir / "PLAN.md").write_text(plan_content, encoding="utf-8")

    # Write empty feedback file
    feedback_path = project_dir / "FEEDBACK.md"
    if not feedback_path.exists():
        feedback_path.write_text(
            "# Feedback\n\nAdd your feedback here after reviewing the preliminary outputs.\n",
            encoding="utf-8",
        )

    # Init git
    _run(["git", "init"], cwd=project_dir)
    _run(["git", "add", "."], cwd=project_dir)
    _run(["git", "commit", "-m", "init: project setup"], cwd=project_dir)

    # Create GitHub repo
    github_url = _create_github_repo(project_name, brief, project_dir)

    logger.info(f"[project_manager] Project ready: {project_dir}")
    return {"project_dir": str(project_dir), "github_url": github_url}


def push(project_dir: Path, message: str = "chore: update") -> None:
    """Stage all changes and push to GitHub."""
    _run(["git", "add", "-A"], cwd=project_dir)
    result = subprocess.run(
        ["git", "diff", "--staged", "--quiet"],
        cwd=project_dir, capture_output=True
    )
    if result.returncode != 0:
        _run(["git", "commit", "-m", message], cwd=project_dir)
    _run(["git", "pull", "--rebase", "origin", "main"], cwd=project_dir)
    _run(["git", "push"], cwd=project_dir)
    logger.info(f"[project_manager] Pushed → {project_dir.name}")


def _create_github_repo(project_name: str, description: str, project_dir: Path) -> str:
    """Create public GitHub repo and push. Returns the repo URL."""
    short_desc = description[:100].replace('"', "'").split("\n")[0]
    try:
        result = subprocess.run(
            [GH_CLI, "repo", "create", f"{GITHUB_USER}/{project_name}",
             "--public", "--description", short_desc, "--source", str(project_dir),
             "--remote", "origin", "--push"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            url = f"https://github.com/{GITHUB_USER}/{project_name}"
            logger.info(f"[project_manager] GitHub repo created: {url}")
            return url
        else:
            logger.warning(f"[project_manager] gh repo create failed: {result.stderr}")
            return ""
    except Exception as e:
        logger.warning(f"[project_manager] Could not create GitHub repo: {e}")
        return ""


def _run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, capture_output=True)
