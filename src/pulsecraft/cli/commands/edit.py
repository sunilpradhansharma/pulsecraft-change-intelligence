"""edit command — record an operator edit on a pending HITL item."""

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
    @app.command("edit")
    def edit(
        change_id: str = typer.Argument(  # noqa: B008
            ...,
            help="change_id (full UUID or first 8 chars) of the pending HITL item.",
        ),
        field: str = typer.Option(  # noqa: B008
            ...,
            "--field",
            help="Dot-path of the field to edit (e.g. message_variants.teams_medium).",
        ),
        value: str = typer.Option(  # noqa: B008
            ...,
            "--value",
            help="New value for the field.",
        ),
        reviewer: str = typer.Option(  # noqa: B008
            None,
            "--reviewer",
            help="Reviewer name for audit. Defaults to $USER.",
        ),
        audit_dir: Path = typer.Option(DEFAULT_AUDIT_DIR, "--audit-dir"),  # noqa: B008
        queue_dir: Path = typer.Option(DEFAULT_QUEUE_DIR, "--queue-dir"),  # noqa: B008
        output_json: bool = typer.Option(False, "--json", help="Output result as JSON."),  # noqa: B008
    ) -> None:
        """Record an operator edit on a HITL-pending item.

        V1: logs the edit intent to audit. Does not re-run downstream gates.
        Full downstream-re-run will be handled in a future prompt.
        """
        from pulsecraft.cli.common import load_hitl_queue

        full_id = resolve_change_id(change_id, audit_dir)
        reviewer_name = reviewer or reviewer_from_env()
        queue = load_hitl_queue(queue_dir, audit_dir)

        if not queue.is_pending(full_id):
            err_console.print(f"[red]Not found in pending queue:[/red] {full_id}")
            raise typer.Exit(code=2)

        try:
            queue.edit(full_id, field_path=field, new_value=value, reviewer=reviewer_name)
        except Exception as exc:
            err_console.print(f"[red]Edit failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output(
                {
                    "change_id": full_id,
                    "action": "edited",
                    "field": field,
                    "value": value,
                    "reviewer": reviewer_name,
                }
            )
        else:
            console.print(
                Panel(
                    f"[cyan]Edited[/cyan]     {full_id}\n"
                    f"Field:     {field}\n"
                    f"Value:     {value}\n"
                    f"Reviewer:  {reviewer_name}\n\n"
                    "[dim]Edit recorded in audit. Re-run downstream gates: future prompt.[/dim]",
                    title="HITL edit recorded",
                )
            )
