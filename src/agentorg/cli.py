"""Command-line entry point for the agentorg system."""

from __future__ import annotations

import importlib

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

app = typer.Typer(
    name="agentorg",
    help="Autonomous multi-agent research organization.",
)
console = Console()

ROLES = ["planner", "builder", "verifier", "reporter", "debugger", "qual_builder", "quant_builder"]


@app.command()
def run(
    role: str = typer.Argument(help=f"Agent role to run: {' | '.join(ROLES)}"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without executing"),
    time_budget: str = typer.Option("", "--time-budget", "-t", help="Time budget e.g. 5m, 2h"),
) -> None:
    """Run a specific agent role."""
    if role not in ROLES:
        console.print(f"[red]Unknown role '{role}'. Valid roles: {', '.join(ROLES)}[/red]")
        raise typer.Exit(1)

    if time_budget:
        import os
        os.environ["TIME_BUDGET"] = time_budget
        import agentorg.config as _cfg
        _cfg.TIME_BUDGET = time_budget

    console.print(f"[bold green]Starting agent:[/bold green] {role}")

    module = importlib.import_module(f"agentorg.agents.{role}")
    if role == "debugger":
        module.main(dry_run=dry_run)
    else:
        # Convert snake_case to PascalCase: qual_builder → QualBuilderAgent
        class_name = "".join(word.capitalize() for word in role.split("_")) + "Agent"
        agent_class = getattr(module, class_name)
        agent = agent_class()
        agent.run_with_recovery(dry_run=dry_run)


@app.command()
def new(
    brief: str = typer.Argument(help="Task brief — what you want the team to do"),
) -> None:
    """
    Start a new project: design a custom agent team, create a project repo,
    and write PLAN.md for approval.
    """
    from agentorg.agents.team_planner import TeamPlannerAgent
    from agentorg import session_state

    console.print(Panel(f"[bold]New Project[/bold]\n\n{brief}", title="Brief"))
    console.print("[cyan]Designing your team...[/cyan]")

    planner = TeamPlannerAgent()
    plan = planner.plan(brief)

    project_name = plan.get("project_name", "untitled-project")

    # Create project directory + GitHub repo
    from agentorg.project_manager import create_project, PROJECTS_ROOT
    import tempfile
    from pathlib import Path

    project_dir = PROJECTS_ROOT / project_name
    plan_path = project_dir / "PLAN.md" if project_dir.exists() else Path(tempfile.mktemp(suffix=".md"))

    # Write plan markdown first (we need project_dir to exist)
    project_dir.mkdir(parents=True, exist_ok=True)
    planner.write_plan_md(brief, plan, project_dir / "PLAN.md")

    result = create_project(project_name, brief, (project_dir / "PLAN.md").read_text())

    # Save session state
    session = session_state.ProjectSession(
        name=project_name,
        brief=brief,
        project_dir=result["project_dir"],
        github_url=result["github_url"],
        phase="planning",
        team=plan["team"],
    )
    session_state.save(session)

    # Display plan
    plan_md = (project_dir / "PLAN.md").read_text(encoding="utf-8")
    console.print(Markdown(plan_md))

    if result["github_url"]:
        console.print(f"\n[green]Repo:[/green] {result['github_url']}")
    console.print(f"[green]Local:[/green] {result['project_dir']}")
    console.print("\n[bold yellow]Tell me 'approve' to start the preliminary run, or tell me what to change.[/bold yellow]")


@app.command()
def prelim() -> None:
    """
    Run the preliminary pass: fast, cheap models, <10 min.
    Requires an active session (run `agentorg new` first).
    """
    from agentorg import session_state, runner

    session = session_state.load()
    if not session:
        console.print("[red]No active session. Run `agentorg new <brief>` first.[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Preliminary run:[/bold cyan] {session.name}")
    console.print("[dim]Using fast/cheap models — target <10 min[/dim]\n")

    result = runner.run_prelim(session)

    session.phase = "prelim"
    session.completed_phases.append("prelim")
    session.last_outputs = result.get("outputs", [])
    session_state.save(session)

    elapsed = result.get("elapsed_seconds", 0)
    console.print(f"\n[green]Preliminary run complete[/green] — {elapsed // 60}m {elapsed % 60}s")
    if session.github_url:
        console.print(f"[green]Results:[/green] {session.github_url}")
    console.print(f"[dim]Local reports:[/dim] {session.project_dir}/reports/")
    console.print("\n[bold yellow]Review the outputs and tell me your feedback, or say 'go deeper'.[/bold yellow]")


@app.command()
def iterate(
    feedback: str = typer.Argument(default="", help="Feedback or instruction for the next run"),
) -> None:
    """
    Run a deeper pass with optional feedback incorporated.
    Reads FEEDBACK.md from the project dir if no feedback argument given.
    """
    from agentorg import session_state, runner
    from pathlib import Path

    session = session_state.load()
    if not session:
        console.print("[red]No active session.[/red]")
        raise typer.Exit(1)

    # Read feedback from file if not passed as arg
    if not feedback:
        feedback_path = Path(session.project_dir) / "FEEDBACK.md"
        if feedback_path.exists():
            raw = feedback_path.read_text(encoding="utf-8")
            # Skip the header line
            lines = [l for l in raw.splitlines() if not l.startswith("#") and l.strip()]
            feedback = "\n".join(lines).strip()

    console.print(f"[bold cyan]Deep run:[/bold cyan] {session.name}")
    if feedback:
        console.print(f"[dim]Incorporating feedback:[/dim] {feedback[:120]}...")

    result = runner.run_deep(session, feedback=feedback)

    session.phase = "deep"
    session.completed_phases.append("deep")
    session.last_outputs = result.get("outputs", [])
    session.pending_feedback = ""
    session_state.save(session)

    elapsed = result.get("elapsed_seconds", 0)
    console.print(f"\n[green]Deep run complete[/green] — {elapsed // 60}m {elapsed % 60}s")
    if session.github_url:
        console.print(f"[green]Results:[/green] {session.github_url}")


@app.command()
def status() -> None:
    """Show active session and recent reports."""
    from agentorg import session_state
    import datetime
    import os
    from agentorg.config import REPORTS_DIR

    # Active session
    session = session_state.load()
    if session and session.phase != "done":
        console.print(Panel(
            f"[bold]{session.name}[/bold]\n"
            f"Phase: {session.phase} | Team: {', '.join(session.team)}\n"
            f"Last run: {session.last_run[:16].replace('T', ' ') if session.last_run else 'never'}\n"
            f"Repo: {session.github_url or 'not created yet'}",
            title="Active Session"
        ))
    else:
        console.print("[dim]No active session.[/dim]")

    # Recent reports
    reports_dir = REPORTS_DIR
    if session and session.phase != "done":
        from pathlib import Path
        reports_dir = Path(session.project_dir) / "reports"

    table = Table(title="Recent Reports", show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Size", justify="right")
    table.add_column("Modified", style="green")

    if reports_dir.exists():
        files = sorted(reports_dir.glob("*.md"), key=os.path.getmtime, reverse=True)[:8]
        for f in files:
            stat = f.stat()
            modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(f.name, f"{stat.st_size:,}b", modified)
    console.print(table)


@app.command()
def done() -> None:
    """Mark the current project as complete and clear session state."""
    from agentorg import session_state
    session = session_state.load()
    if session:
        console.print(f"[green]Marking '{session.name}' as done.[/green]")
        session_state.clear()
    else:
        console.print("[dim]No active session.[/dim]")


@app.command()
def session(
    time_budget: str = typer.Option("", "--time-budget", "-t"),
    turns: int = typer.Option(0, "--turns"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Run a collaborative research session (qual + quant in parallel)."""
    from agentorg.agents.session import run_collaborative_session

    console.print("[bold green]Starting collaborative session[/bold green]")
    result = run_collaborative_session(
        time_budget=time_budget,
        turns_per_agent=turns or None,
        dry_run=dry_run,
    )
    console.print(f"[green]Session complete[/green] — {result.get('messages', 0)} messages, "
                  f"{len(result.get('charts', []))} charts")


@app.command()
def export(
    format: str = typer.Option("both", help="markdown | pdf | both"),
    out: str = typer.Option("reports/", help="Output directory"),
) -> None:
    """Export latest reports to Markdown and/or PDF."""
    from agentorg.reporting.generator import ReportGenerator
    gen = ReportGenerator(output_dir=out)
    gen.export(format=format)
    console.print(f"[green]Export complete → {out}[/green]")


if __name__ == "__main__":
    app()
