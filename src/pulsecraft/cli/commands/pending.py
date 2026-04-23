"""pending command — list HITL-pending items."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pulsecraft.cli.common import (
    DEFAULT_AUDIT_DIR,
    DEFAULT_QUEUE_DIR,
    truncate,
)

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("pending")
    def pending(
        audit_dir: Path = typer.Option(DEFAULT_AUDIT_DIR, "--audit-dir"),  # noqa: B008
        queue_dir: Path = typer.Option(DEFAULT_QUEUE_DIR, "--queue-dir"),  # noqa: B008
        reason_filter: str = typer.Option(  # noqa: B008
            None,
            "--reason",
            help="Filter by HITL reason (substring match).",
        ),
        since: str = typer.Option(  # noqa: B008
            None,
            "--since",
            help="Only show items enqueued on or after this date (YYYY-MM-DD).",
        ),
        limit: int = typer.Option(50, "--limit", help="Maximum rows to show."),  # noqa: B008
        output_json: bool = typer.Option(False, "--json", help="Output as JSON array."),  # noqa: B008
    ) -> None:
        """List all HITL-pending items.

        Shows change_id, received_at, reason, and a short snippet.
        Use pulsecraft approve / reject / edit to act on items.
        """
        from pulsecraft.cli.common import load_hitl_queue

        queue = load_hitl_queue(queue_dir, audit_dir)
        items = queue.list_pending()

        # Apply filters
        if reason_filter:
            items = [i for i in items if reason_filter.lower() in i.reason.lower()]

        if since:
            try:
                since_dt = datetime.fromisoformat(since).replace(tzinfo=UTC)
                items = [
                    i
                    for i in items
                    if datetime.fromisoformat(i.enqueued_at.rstrip("Z").replace("Z", "+00:00"))
                    >= since_dt
                ]
            except ValueError:
                err_console.print(f"[red]Invalid --since date:[/red] {since!r} — use YYYY-MM-DD")
                raise typer.Exit(code=1) from None

        items = items[:limit]

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output([i.to_dict() for i in items])
            return

        if not items:
            console.print("[dim]No pending HITL items.[/dim]")
            return

        table = Table(title=f"HITL pending ({len(items)} item{'s' if len(items) != 1 else ''})")
        table.add_column("change_id", style="cyan", no_wrap=True)
        table.add_column("Enqueued at", style="dim")
        table.add_column("Reason", style="yellow")
        table.add_column("Status")
        table.add_column("Snippet")

        for item in items:
            short_id = item.change_id[:8]
            snippet = truncate(str(item.payload), 60)
            table.add_row(
                short_id,
                item.enqueued_at[:19].replace("T", " "),
                item.reason,
                item.status,
                snippet,
            )

        console.print(table)
        console.print(
            "\nRun [bold]pulsecraft approve <change-id>[/bold] or "
            "[bold]pulsecraft reject <change-id> --reason <text>[/bold] to act."
        )
