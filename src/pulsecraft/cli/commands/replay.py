"""replay command — re-run a change from saved inputs."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from pulsecraft.cli.common import DEFAULT_AUDIT_DIR, DEFAULT_QUEUE_DIR, resolve_change_id

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("replay")
    def replay(
        change_id: str = typer.Argument(  # noqa: B008
            ...,
            help="change_id (full UUID or first 8 chars) to replay.",
        ),
        fixture_root: Path = typer.Option(  # noqa: B008
            Path("fixtures/changes"),
            "--fixture-root",
            help="Root directory to search for the ChangeArtifact JSON.",
        ),
        audit_dir: Path = typer.Option(DEFAULT_AUDIT_DIR, "--audit-dir"),  # noqa: B008
        queue_dir: Path = typer.Option(DEFAULT_QUEUE_DIR, "--queue-dir"),  # noqa: B008
        real_signalscribe: bool = typer.Option(False, "--real-signalscribe"),  # noqa: B008
        real_buatlas: bool = typer.Option(False, "--real-buatlas"),  # noqa: B008
        real_pushpilot: bool = typer.Option(False, "--real-pushpilot"),  # noqa: B008
    ) -> None:
        """Re-run a change from saved inputs.

        Searches fixture-root (and its generated/ subdirectory) for the
        ChangeArtifact JSON for the given change_id, then re-runs the pipeline
        with a fresh orchestrator state. Useful for testing prompt changes or
        comparing agent versions across runs.
        """
        import json

        from pulsecraft.orchestrator.audit import AuditWriter
        from pulsecraft.orchestrator.engine import Orchestrator
        from pulsecraft.orchestrator.hitl import HITLQueue
        from pulsecraft.orchestrator.mock_agents import MockBUAtlas, MockPushPilot, MockSignalScribe
        from pulsecraft.schemas.change_artifact import ChangeArtifact

        full_id = resolve_change_id(change_id, audit_dir)

        # Search for fixture file
        artifact: ChangeArtifact | None = None
        search_dirs = [fixture_root, fixture_root / "generated"]
        for search_dir in search_dirs:
            candidate = search_dir / f"{full_id}.json"
            if candidate.exists():
                try:
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                    artifact = ChangeArtifact.model_validate(raw)
                    break
                except Exception:
                    continue

        if artifact is None:
            err_console.print(
                f"[red]Fixture not found:[/red] {full_id}\n"
                f"Searched: {', '.join(str(d) for d in search_dirs)}"
            )
            raise typer.Exit(code=2)

        console.print(
            Panel(
                f"[bold]change_id:[/bold]  {artifact.change_id}\n"
                f"[bold]title:[/bold]      {artifact.title}\n"
                f"[bold]source:[/bold]     {artifact.source_type}",
                title="[bold yellow]PulseCraft REPLAY[/bold yellow]",
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
                title="Replay result",
                subtitle=f"{result.audit_record_count} new audit records written",
            )
        )
