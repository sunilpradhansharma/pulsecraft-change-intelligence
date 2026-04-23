"""metrics command — aggregate pipeline metrics over a time window."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pulsecraft.cli.common import DEFAULT_AUDIT_DIR

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("metrics")
    def metrics(
        audit_dir: Path = typer.Option(DEFAULT_AUDIT_DIR, "--audit-dir"),  # noqa: B008
        since: str = typer.Option(  # noqa: B008
            None,
            "--since",
            help="Start of window (YYYY-MM-DD). Defaults to 7 days ago.",
        ),
        until: str = typer.Option(  # noqa: B008
            None,
            "--until",
            help="End of window (YYYY-MM-DD). Defaults to now.",
        ),
        bu_filter: str = typer.Option(  # noqa: B008
            None,
            "--bu-id",
            help="Filter delivery metrics by bu_id.",
        ),
        output_json: bool = typer.Option(False, "--json", help="Output as JSON."),  # noqa: B008
    ) -> None:
        """Aggregate pipeline metrics over a time window.

        Reads all audit records in the window and summarizes:
        terminal state distribution, agent invocation counts, HITL trigger
        rates, latency, and most-notified BUs.
        """
        from pulsecraft.orchestrator.audit import AuditWriter
        from pulsecraft.schemas.audit_record import EventType

        now = datetime.now(UTC)
        since_dt = _parse_date(since, now - timedelta(days=7))
        until_dt = _parse_date(until, now)

        audit_writer = AuditWriter(root=audit_dir)

        if not audit_dir.exists():
            console.print("[dim]No audit records found.[/dim]")
            return

        # Collect all change_ids in window
        all_change_ids: set[str] = set()
        for day_dir in sorted(audit_dir.iterdir()):
            if not day_dir.is_dir():
                continue
            for p in day_dir.glob("*.jsonl"):
                all_change_ids.add(p.stem)

        if not all_change_ids:
            console.print("[dim]No changes found in audit directory.[/dim]")
            return

        # Aggregate per-change data
        terminal_states: Counter[str] = Counter()
        agent_invocations: Counter[str] = Counter()
        hitl_reasons: Counter[str] = Counter()
        bu_deliveries: Counter[str] = Counter()
        latencies_ms: list[float] = []
        total_cost = 0.0
        changes_in_window = 0

        for change_id in all_change_ids:
            records = audit_writer.read_chain(change_id)
            if not records:
                continue

            # Filter to window
            in_window = [r for r in records if since_dt <= r.timestamp <= until_dt]
            if not in_window:
                continue

            changes_in_window += 1

            first_ts = in_window[0].timestamp
            last_ts = in_window[-1].timestamp
            delta_ms = (last_ts - first_ts).total_seconds() * 1000
            latencies_ms.append(delta_ms)

            terminal: str | None = None
            for r in in_window:
                if r.event_type == EventType.AGENT_INVOCATION:
                    agent = r.actor.id.replace("_mock", "")
                    agent_invocations[agent] += 1
                    if r.metrics and r.metrics.cost_usd:
                        total_cost += r.metrics.cost_usd

                elif r.event_type == EventType.HITL_ACTION and r.action == "enqueued":
                    reason = _extract_hitl_reason(r.output_summary)
                    hitl_reasons[reason] += 1

                elif r.event_type == EventType.DELIVERY_ATTEMPT:
                    bu_id = _extract_kv(r.output_summary, "bu_id")
                    if bu_id and (not bu_filter or bu_filter.lower() in bu_id.lower()):
                        bu_deliveries[bu_id] += 1

                elif r.event_type == EventType.STATE_TRANSITION:
                    arrow = " → "
                    if arrow in r.output_summary:
                        _, rest = r.output_summary.split(arrow, 1)
                        to_state = rest.split(":")[0].strip()
                        terminal = to_state

            if terminal:
                terminal_states[terminal] += 1

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output(
                {
                    "window": {
                        "since": since_dt.isoformat(),
                        "until": until_dt.isoformat(),
                    },
                    "changes_in_window": changes_in_window,
                    "terminal_states": dict(terminal_states),
                    "agent_invocations": dict(agent_invocations),
                    "total_cost_usd": round(total_cost, 6),
                    "hitl_reasons": dict(hitl_reasons),
                    "bu_deliveries": dict(bu_deliveries),
                    "latency_p50_ms": round(median(latencies_ms), 1) if latencies_ms else None,
                    "latency_p95_ms": (round(_p95(latencies_ms), 1) if latencies_ms else None),
                }
            )
            return

        # Rich output
        window_str = f"{since_dt.strftime('%Y-%m-%d')} → {until_dt.strftime('%Y-%m-%d')}"
        console.print(
            Panel(
                f"Window:  {window_str}\n"
                f"Changes: {changes_in_window}  ·  "
                f"Total cost: ${total_cost:.4f}",
                title="PulseCraft metrics",
            )
        )

        # Terminal state distribution
        if terminal_states:
            t_table = Table(title="Terminal state distribution")
            t_table.add_column("State", style="cyan")
            t_table.add_column("Count", justify="right")
            for state, count in terminal_states.most_common():
                t_table.add_row(state, str(count))
            console.print(t_table)

        # Agent invocations
        if agent_invocations:
            a_table = Table(title="Agent invocations")
            a_table.add_column("Agent", style="yellow")
            a_table.add_column("Invocations", justify="right")
            for agent, count in agent_invocations.most_common():
                a_table.add_row(agent, str(count))
            console.print(a_table)

        # HITL triggers
        if hitl_reasons:
            h_table = Table(title="HITL triggers by reason")
            h_table.add_column("Reason", style="yellow")
            h_table.add_column("Count", justify="right")
            for reason, count in hitl_reasons.most_common():
                h_table.add_row(reason, str(count))
            console.print(h_table)

        # Latency
        if latencies_ms:
            p50 = median(latencies_ms)
            p95 = _p95(latencies_ms)
            console.print(
                f"\nLatency: P50 = {p50 / 1000:.1f}s · P95 = {p95 / 1000:.1f}s "
                f"(across {len(latencies_ms)} change{'s' if len(latencies_ms) != 1 else ''})"
            )

        # Top BUs
        if bu_deliveries:
            b_table = Table(title="Most-notified BUs")
            b_table.add_column("BU ID", style="cyan")
            b_table.add_column("Deliveries", justify="right")
            for bu_id, count in bu_deliveries.most_common(10):
                b_table.add_row(bu_id, str(count))
            console.print(b_table)


def _parse_date(s: str | None, default: datetime) -> datetime:
    if s is None:
        return default
    try:
        return datetime.fromisoformat(s).replace(tzinfo=UTC)
    except ValueError:
        err_console = Console(stderr=True)
        err_console.print(f"[red]Invalid date:[/red] {s!r} — use YYYY-MM-DD")
        raise typer.Exit(code=1) from None


def _extract_kv(text: str, key: str) -> str | None:
    import re

    m = re.search(rf"\b{re.escape(key)}=(\S+)", text)
    return m.group(1) if m else None


def _extract_hitl_reason(output_summary: str) -> str:
    # Format: "Enqueued for HITL review: reason=<reason>"
    val = _extract_kv(output_summary, "reason")
    return val or output_summary[:40]


def _p95(values: list[float]) -> float:
    sorted_vals = sorted(values)
    idx = int(len(sorted_vals) * 0.95)
    return sorted_vals[min(idx, len(sorted_vals) - 1)]
