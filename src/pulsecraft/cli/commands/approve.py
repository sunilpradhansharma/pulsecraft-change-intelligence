"""approve command — approve a HITL-pending change and move it to approved/."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from pulsecraft.cli.common import (
    DEFAULT_AUDIT_DIR,
    DEFAULT_QUEUE_DIR,
    resolve_change_id,
    reviewer_from_env,
)

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("approve")
    def approve(
        change_id: str = typer.Argument(  # noqa: B008
            ...,
            help="change_id (full UUID or first 8 chars) of the pending HITL item.",
        ),
        reviewer: str = typer.Option(  # noqa: B008
            None,
            "--reviewer",
            help="Reviewer name for audit. Defaults to $USER.",
        ),
        notes: str = typer.Option(  # noqa: B008
            None,
            "--notes",
            help="Optional reviewer notes.",
        ),
        audit_dir: Path = typer.Option(DEFAULT_AUDIT_DIR, "--audit-dir"),  # noqa: B008
        queue_dir: Path = typer.Option(DEFAULT_QUEUE_DIR, "--queue-dir"),  # noqa: B008
        output_json: bool = typer.Option(False, "--json", help="Output result as JSON."),  # noqa: B008
    ) -> None:
        """Approve a HITL-pending change.

        Moves the item from queue/hitl/pending/ to queue/hitl/approved/ and
        writes a hitl_action audit record. Pipeline resumption after approval
        is handled in a future prompt.
        """
        from pulsecraft.cli.common import load_hitl_queue

        full_id = resolve_change_id(change_id, audit_dir)
        reviewer_name = reviewer or reviewer_from_env()
        queue = load_hitl_queue(queue_dir, audit_dir)

        if not queue.is_pending(full_id):
            err_console.print(
                f"[red]Not found in pending queue:[/red] {full_id}\n"
                "Run [bold]pulsecraft pending[/bold] to see pending items."
            )
            raise typer.Exit(code=2)

        try:
            queue.approve(full_id, reviewer=reviewer_name, notes=notes)
        except Exception as exc:
            err_console.print(f"[red]Approve failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output(
                {
                    "change_id": full_id,
                    "action": "approved",
                    "reviewer": reviewer_name,
                    "notes": notes,
                }
            )
        else:
            console.print(
                Panel(
                    f"[green]Approved[/green]  {full_id}\n"
                    f"Reviewer:  {reviewer_name}\n"
                    f"Notes:     {notes or '—'}\n\n"
                    "Item moved to queue/hitl/approved/\n"
                    "Run [bold]pulsecraft explain[/bold] to see the full decision trail.",
                    title="HITL approved",
                )
            )
