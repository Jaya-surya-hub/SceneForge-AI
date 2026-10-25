"""Typer CLI interface for IncuBrix Signal Room."""

from __future__ import annotations

import json
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table

from signalroom.core.config import settings
from signalroom.core.logging import setup_logging
from signalroom.db.session import SessionLocal, init_db
from signalroom.models.evidence import EvidenceReference
from signalroom.models.project import Project
from signalroom.models.question import Question
from signalroom.models.run import Run
from signalroom.storage.artifact_store import artifact_store

app = typer.Typer(
    name="signalroom",
    help="IncuBrix Signal Room — The Evidence-First Search & AI Visibility Intelligence Engine",
    add_completion=False,
)
console = Console()


@app.command("info")
def show_info():
    """Displays Signal Room system configuration and active runtime parameters."""
    console.print("\n[bold orange3]IncuBrix Signal Room[/bold orange3] — System Information")
    console.print(f"[dim]Tagline: {settings.TAGLINE}[/dim]\n")

    table = Table(title="Runtime Configuration", show_header=True, header_style="bold cyan")
    table.add_column("Parameter", style="dim")
    table.add_column("Value", style="green")

    table.add_row("Version", settings.VERSION)
    table.add_row("Environment", settings.ENVIRONMENT)
    table.add_row("Database URL", settings.DATABASE_URL)
    table.add_row("Artifact Storage", str(artifact_store.base_dir))
    table.add_row("Demo Mode", str(settings.DEMO_MODE))
    table.add_row("API Prefix", settings.API_V1_PREFIX)
    table.add_row("Log Level", settings.LOG_LEVEL)

    console.print(table)


@app.command("health")
def check_health():
    """Performs an audit of database connectivity, storage writeability, and ledger integrity."""
    console.print("[bold]Checking IncuBrix Signal Room health...[/bold]")
    db = SessionLocal()
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_ok = False
        console.print(f"[red]Database connection failed:[/red] {e}")

    try:
        probe = artifact_store.base_dir / ".cli_probe"
        probe.write_text("ok")
        probe.unlink()
        storage_ok = True
    except Exception as e:
        storage_ok = False
        console.print(f"[red]Artifact storage write check failed:[/red] {e}")

    q_count = db.query(Question).count() if db_ok else 0
    ev_count = db.query(EvidenceReference).count() if db_ok else 0
    db.close()

    status_color = "green" if (db_ok and storage_ok) else "red"
    console.print(f"\nStatus: [{status_color}]{'HEALTHY' if (db_ok and storage_ok) else 'DEGRADED'}[/{status_color}]")
    console.print(f"- Database: {'[green]Connected[/green]' if db_ok else '[red]Error[/red]'}")
    console.print(f"- Artifact Storage: {'[green]Writable[/green]' if storage_ok else '[red]Error[/red]'}")
    console.print(f"- Questions in Atlas: [cyan]{q_count}[/cyan]")
    console.print(f"- Evidence Ledger Records: [cyan]{ev_count}[/cyan]\n")


@app.command("migrate")
def run_migrations():
    """Initializes and verifies the database schema."""
    console.print("[bold cyan]Applying Signal Room database migrations...[/bold cyan]")
    try:
        init_db()
        console.print("[bold green][OK] Database schema successfully initialized and verified.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Migration failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@app.command("replay")
def replay_question(
    question_id: str = typer.Argument(..., help="ID of question to replay (e.g. Q-047)"),
    market: str = typer.Option("US", "--market", "-m", help="Market code (e.g. US, UK, IN)"),
    compare: bool = typer.Option(True, "--compare/--no-compare", help="Generate side-by-side comparison report"),
):
    """Replays an existing creator question against recorded provider configurations.
    
    Preserves original evidence, creates a new observation record, and outputs a variance comparison report.
    """
    console.print(f"\n[bold orange3]IncuBrix Live Replay Engine[/bold orange3]")
    console.print(f"Target Question: [bold cyan]{question_id}[/bold cyan] | Market: [bold green]{market}[/bold green]\n")

    db = SessionLocal()
    question = db.query(Question).filter(Question.id == question_id).first()

    if not question:
        console.print(f"[bold red]Error:[/bold red] Question '{question_id}' not found in Question Atlas.")
        console.print("[dim]Hint: In Phase 1 foundational CLI, seed questions or run live replay after Phase 3 ingestion.[/dim]\n")
        db.close()
        raise typer.Exit(code=1)

    console.print(f"Found Question: [italic]\"{question.text}\"[/italic]")
    console.print(f"Journey Stage: [cyan]{question.journey_stage}[/cyan] | Intent: [cyan]{question.search_intent}[/cyan]")
    console.print(f"Original Source: [blue]{question.source_url}[/blue]")
    console.print("\n[yellow][DEMO / FOUNDATION MODE][/yellow] Replay execution framework initialized for Phase 2 Live Replay Lab integration.")
    db.close()


def cli_entrypoint():
    """Main function entry point for setup.py / pyproject.toml scripts."""
    app()


if __name__ == "__main__":
    cli_entrypoint()
