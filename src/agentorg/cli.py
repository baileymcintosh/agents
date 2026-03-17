"""Command-line entry point for the agentorg system."""

from __future__ import annotations

import importlib

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="agentorg",
    help="Autonomous multi-agent research organization — run agents, check status, export reports.",
)
console = Console()

ROLES = ["planner", "builder", "verifier", "reporter", "debugger"]


@app.command()
def run(
    role: str = typer.Argument(help=f"Agent role to run: {' | '.join(ROLES)}"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print plan without executing"),
) -> None:
    """Run a specific agent role."""
    if role not in ROLES:
        console.print(f"[red]Unknown role '{role}'. Valid roles: {', '.join(ROLES)}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold green]Starting agent:[/bold green] {role}")
    if dry_run:
        console.print("[yellow]Dry-run mode — no changes will be made.[/yellow]")

    module = importlib.import_module(f"agentorg.agents.{role}")
    if role == "debugger":
        # Debugger runs its own main() (post-failure mode)
        module.main(dry_run=dry_run)  # type: ignore[attr-defined]
    else:
        # All other agents use run_with_recovery for inline debugger support
        agent_class = getattr(module, f"{role.capitalize()}Agent")
        agent = agent_class()
        agent.run_with_recovery(dry_run=dry_run)


@app.command()
def status() -> None:
    """Show recent reports and system status."""
    import datetime
    import os
    from agentorg.config import REPORTS_DIR

    table = Table(title="Recent Reports", show_header=True, header_style="bold magenta")
    table.add_column("File", style="cyan", no_wrap=True)
    table.add_column("Size", justify="right")
    table.add_column("Modified", style="green")

    if REPORTS_DIR.exists():
        files = sorted(REPORTS_DIR.glob("*.md"), key=os.path.getmtime, reverse=True)[:10]
        for f in files:
            stat = f.stat()
            modified = datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            table.add_row(f.name, f"{stat.st_size:,}b", modified)
        if not files:
            console.print("[dim]No reports found yet. Run an agent to generate one.[/dim]")
    else:
        console.print("[dim]Reports directory not found.[/dim]")

    console.print(table)


@app.command()
def export(
    format: str = typer.Option("both", help="Export format: markdown | pdf | both"),
    out: str = typer.Option("reports/", help="Output directory"),
) -> None:
    """Export the latest reports to Markdown and/or PDF."""
    from agentorg.reporting.generator import ReportGenerator

    gen = ReportGenerator(output_dir=out)
    gen.export(format=format)
    console.print(f"[green]Export complete → {out}[/green]")


if __name__ == "__main__":
    app()
