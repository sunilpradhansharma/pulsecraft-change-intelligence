"""audit command — print the audit chain for a change_id."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pulsecraft.cli.common import DEFAULT_AUDIT_DIR, resolve_change_id, truncate

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("audit")
    def audit_cmd(
        change_id: str = typer.Argument(  # noqa: B008
            ...,
            help="change_id (full UUID or first 8 chars).",
        ),
        audit_dir: Path = typer.Option(DEFAULT_AUDIT_DIR, "--audit-dir"),  # noqa: B008
        event_type_filter: str = typer.Option(  # noqa: B008
            None,
            "--event-type",
            help="Filter records by event_type (substring match).",
        ),
        since: str = typer.Option(  # noqa: B008
            None,
            "--since",
            help="Only show records on or after this date (YYYY-MM-DD).",
        ),
        output_json: bool = typer.Option(
            False, "--json", help="Dump full AuditRecord objects as JSON."
        ),  # noqa: B008
        list_ids: bool = typer.Option(False, "--list", help="List all known change_ids."),  # noqa: B008
    ) -> None:
        """Print the audit chain for a change_id.

        Reads all JSONL records for the given change_id across all date shards and
        shows a formatted table. Pass --json to dump full AuditRecord objects.
        Pass --list to enumerate all known change_ids without reading a chain.
        """
        from pulsecraft.cli.common import load_audit_writer

        audit_writer = load_audit_writer(audit_dir)

        if list_ids:
            _list_change_ids(audit_dir)
            return

        full_id = resolve_change_id(change_id, audit_dir)
        records = audit_writer.read_chain(full_id)

        # Filters
        if event_type_filter:
            records = [r for r in records if event_type_filter.lower() in r.event_type.lower()]

        if since:
            from datetime import UTC, datetime

            try:
                since_dt = datetime.fromisoformat(since).replace(tzinfo=UTC)
                records = [r for r in records if r.timestamp >= since_dt]
            except ValueError:
                err_console.print(f"[red]Invalid --since date:[/red] {since!r}")
                raise typer.Exit(code=1) from None

        if not records:
            console.print(f"[dim]No audit records found for {full_id}[/dim]")
            return

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output([r.model_dump() for r in records])
            return

        table = Table(
            title=f"Audit chain — {full_id[:8]}… ({len(records)} records)",
            show_lines=False,
        )
        table.add_column("Time", style="dim", no_wrap=True)
        table.add_column("Event type", style="cyan")
        table.add_column("Actor", style="yellow")
        table.add_column("Action")
        table.add_column("Decision", style="green")
        table.add_column("Summary")

        for r in records:
            decision_str = f"[{r.decision.verb}]" if r.decision else ""
            table.add_row(
                r.timestamp.strftime("%H:%M:%S.%f")[:-3],
                r.event_type,
                r.actor.id,
                r.action,
                decision_str,
                truncate(r.output_summary, 65),
            )

        console.print(table)


def _list_change_ids(audit_dir: Path) -> None:
    """Enumerate all change_ids found in the audit directory."""
    if not audit_dir.exists():
        console.print("[dim]No audit records found.[/dim]")
        return

    ids: list[str] = []
    for day_dir in sorted(audit_dir.iterdir()):
        if not day_dir.is_dir():
            continue
        for p in day_dir.glob("*.jsonl"):
            ids.append(p.stem)

    if not ids:
        console.print("[dim]No change_ids found in audit directory.[/dim]")
        return

    console.print(f"[bold]{len(ids)} change_id(s) in {audit_dir}:[/bold]")
    for cid in sorted(ids):
        console.print(f"  {cid}")
