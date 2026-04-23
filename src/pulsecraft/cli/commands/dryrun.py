"""dryrun command — run a fixture with mocks for testing (no LLM calls by default)."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("dryrun")
    def dryrun(
        fixture_path: Path = typer.Argument(  # noqa: B008
            ...,
            help="Path to a ChangeArtifact JSON fixture file.",
            exists=True,
            dir_okay=False,
            readable=True,
        ),
        audit_dir: Path = typer.Option(  # noqa: B008
            Path("audit"),
            "--audit-dir",
            help="Directory for audit JSONL output.",
        ),
        queue_dir: Path = typer.Option(  # noqa: B008
            Path("queue/hitl"),
            "--queue-dir",
            help="Directory for HITL queue files.",
        ),
        real_signalscribe: bool = typer.Option(  # noqa: B008
            False,
            "--real-signalscribe",
            help="Use real SignalScribe (LLM). Requires ANTHROPIC_API_KEY.",
        ),
        real_buatlas: bool = typer.Option(  # noqa: B008
            False,
            "--real-buatlas",
            help="Use real BUAtlas (LLM).",
        ),
        real_pushpilot: bool = typer.Option(  # noqa: B008
            False,
            "--real-pushpilot",
            help="Use real PushPilot (LLM).",
        ),
    ) -> None:
        """Run a fixture through the pipeline with loud diagnostic output.

        Same as run-change but announces mock vs. real agents prominently and
        labels the session as a dry run. Useful for testing prompt changes
        without worrying about side effects.
        """
        import json

        from pulsecraft.orchestrator.audit import AuditWriter
        from pulsecraft.orchestrator.engine import Orchestrator
        from pulsecraft.orchestrator.hitl import HITLQueue
        from pulsecraft.orchestrator.mock_agents import MockBUAtlas, MockPushPilot, MockSignalScribe
        from pulsecraft.schemas.change_artifact import ChangeArtifact

        try:
            raw = json.loads(fixture_path.read_text(encoding="utf-8"))
            artifact = ChangeArtifact.model_validate(raw)
        except Exception as exc:
            err_console.print(f"[red]Failed to load fixture:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        mode_lines = []
        mode_lines.append(
            f"[bold]SignalScribe:[/bold] {'[green]real (LLM)[/green]' if real_signalscribe else '[yellow]mock[/yellow]'}"
        )
        mode_lines.append(
            f"[bold]BUAtlas:[/bold]      {'[green]real (LLM)[/green]' if real_buatlas else '[yellow]mock[/yellow]'}"
        )
        mode_lines.append(
            f"[bold]PushPilot:[/bold]    {'[green]real (LLM)[/green]' if real_pushpilot else '[yellow]mock[/yellow]'}"
        )

        console.print(
            Panel(
                f"[bold]change_id:[/bold]  {artifact.change_id}\n"
                f"[bold]title:[/bold]      {artifact.title}\n"
                f"[bold]source:[/bold]     {artifact.source_type}\n\n" + "\n".join(mode_lines),
                title="[bold yellow]PulseCraft DRYRUN[/bold yellow]",
                subtitle=str(fixture_path.name),
            )
        )

        from pulsecraft.orchestrator.agent_protocol import (
            BUAtlasProtocol,
            PushPilotProtocol,
            SignalScribeProtocol,
        )

        signalscribe_agent: SignalScribeProtocol
        buatlas_agent: BUAtlasProtocol
        pushpilot_agent: PushPilotProtocol

        if real_signalscribe:
            from pulsecraft.agents.signalscribe import SignalScribe

            signalscribe_agent = SignalScribe()
        else:
            signalscribe_agent = MockSignalScribe()

        buatlas_fanout_fn = None
        if real_buatlas:
            from pulsecraft.agents.buatlas import BUAtlas
            from pulsecraft.agents.buatlas_fanout import buatlas_fanout_sync

            buatlas_agent = BUAtlas()
            buatlas_fanout_fn = lambda briefs, bus: buatlas_fanout_sync(  # noqa: E731
                briefs, bus, factory=lambda: BUAtlas()
            )
        else:
            buatlas_agent = MockBUAtlas()

        if real_pushpilot:
            from pulsecraft.agents.pushpilot import PushPilot

            pushpilot_agent = PushPilot()
        else:
            pushpilot_agent = MockPushPilot()

        audit_writer = AuditWriter(root=audit_dir)
        hitl_queue = HITLQueue(audit_writer=audit_writer, root=queue_dir)
        orchestrator = Orchestrator(
            signalscribe=signalscribe_agent,
            buatlas=buatlas_agent,
            pushpilot=pushpilot_agent,
            audit_writer=audit_writer,
            hitl_queue=hitl_queue,
            buatlas_fanout_fn=buatlas_fanout_fn,
        )

        result = orchestrator.run_change(artifact)

        from rich.table import Table

        records = audit_writer.read_chain(artifact.change_id)
        table = Table(title="State transitions & events", show_lines=False)
        table.add_column("Time", style="dim", no_wrap=True)
        table.add_column("Event type", style="cyan")
        table.add_column("Actor", style="yellow")
        table.add_column("Decision", style="green")
        table.add_column("Summary")

        for r in records:
            decision_str = f"[{r.decision.verb}]" if r.decision else ""
            table.add_row(
                r.timestamp.strftime("%H:%M:%S.%f")[:-3],
                r.event_type,
                r.actor.id,
                decision_str,
                r.output_summary[:70],
            )
        console.print(table)

        state_color = {
            "DELIVERED": "green",
            "ARCHIVED": "dim",
            "HELD": "yellow",
            "DIGESTED": "blue",
            "AWAITING_HITL": "yellow",
            "REJECTED": "red",
            "FAILED": "red bold",
        }.get(str(result.terminal_state), "white")

        console.print(
            Panel(
                Text(str(result.terminal_state), style=state_color, justify="center"),
                title="[yellow]DRYRUN result[/yellow]",
                subtitle=f"{result.audit_record_count} audit records written",
            )
        )

        raise typer.Exit(code=0)
