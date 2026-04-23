"""digest command — list scheduled digest deliveries."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pulsecraft.cli.common import DEFAULT_QUEUE_DIR

console = Console()
err_console = Console(stderr=True)

_SCHEDULED_DIR_NAME = "scheduled"


def register(app: typer.Typer) -> None:
    @app.command("digest")
    def digest(
        queue_dir: Path = typer.Option(DEFAULT_QUEUE_DIR, "--queue-dir"),  # noqa: B008
        bu_filter: str = typer.Option(  # noqa: B008
            None,
            "--bu-id",
            help="Filter by bu_id (substring match).",
        ),
        output_json: bool = typer.Option(False, "--json", help="Output as JSON array."),  # noqa: B008
    ) -> None:
        """List scheduled digest deliveries.

        Reads queue/scheduled/<YYYY-MM-DD>/*.json files written by the
        orchestrator when PushPilot returns a DIGEST or HOLD_UNTIL decision.
        """
        scheduled_root = queue_dir.parent / _SCHEDULED_DIR_NAME
        items: list[dict] = []

        if scheduled_root.exists():
            for day_dir in sorted(scheduled_root.iterdir()):
                if not day_dir.is_dir():
                    continue
                for p in sorted(day_dir.glob("*.json")):
                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                        items.append(data)
                    except Exception:
                        continue

        if bu_filter:
            items = [i for i in items if bu_filter.lower() in i.get("bu_id", "").lower()]

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output(items)
            return

        if not items:
            console.print("[dim]No scheduled digest deliveries found.[/dim]")
            return

        table = Table(
            title=f"Scheduled deliveries ({len(items)} item{'s' if len(items) != 1 else ''})"
        )
        table.add_column("BU ID", style="cyan")
        table.add_column("Send at", style="dim")
        table.add_column("Channel")
        table.add_column("change_id", style="dim")
        table.add_column("Reason")

        for item in items:
            send_at = item.get("send_at", "?")[:19].replace("T", " ")
            table.add_row(
                item.get("bu_id", "?"),
                send_at,
                item.get("channel", "?"),
                item.get("change_id", "?")[:8],
                item.get("reason", "?")[:50],
            )

        console.print(table)
