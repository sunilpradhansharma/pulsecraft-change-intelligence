"""ingest command — fetch a source artifact and write a ChangeArtifact JSON file."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


def register(app: typer.Typer) -> None:
    @app.command("ingest")
    def ingest(
        source_type: str = typer.Argument(  # noqa: B008
            ...,
            help="Source type: release_note, jira_work_item, ado_work_item, doc, feature_flag, incident",
        ),
        source_ref: str = typer.Argument(  # noqa: B008
            ...,
            help="Source reference identifier (e.g. RN-2026-042, JIRA-ALPHA-1234).",
        ),
        output_dir: Path = typer.Option(  # noqa: B008
            Path("fixtures/changes/generated"),
            "--output-dir",
            help="Directory to write the generated ChangeArtifact JSON file.",
        ),
        run: bool = typer.Option(  # noqa: B008
            False,
            "--run",
            help="After ingest, drive the artifact through the pipeline with mock agents.",
        ),
        audit_dir: Path = typer.Option(  # noqa: B008
            Path("audit"),
            "--audit-dir",
            help="Directory for audit JSONL output (only used with --run).",
        ),
        queue_dir: Path = typer.Option(  # noqa: B008
            Path("queue/hitl"),
            "--queue-dir",
            help="Directory for HITL queue files (only used with --run).",
        ),
    ) -> None:
        """Ingest a source artifact and write a ChangeArtifact JSON file.

        Dispatches to the appropriate adapter based on SOURCE_TYPE. Pass --run to
        also drive the artifact through the pipeline with mock agents.
        """
        from pulsecraft.skills.ingest import (
            IngestMalformed,
            IngestNotFound,
            IngestUnauthorized,
            fetch_doc,
            fetch_feature_flag,
            fetch_incident,
            fetch_release_note,
            fetch_work_item,
        )

        _DISPATCH = {
            "release_note": lambda ref: fetch_release_note(ref),
            "jira_work_item": lambda ref: fetch_work_item(ref, source_type="jira_work_item"),
            "ado_work_item": lambda ref: fetch_work_item(ref, source_type="ado_work_item"),
            "doc": lambda ref: fetch_doc(ref),
            "feature_flag": lambda ref: fetch_feature_flag(ref),
            "incident": lambda ref: fetch_incident(ref),
        }

        if source_type not in _DISPATCH:
            err_console.print(
                f"[red]Unknown source_type:[/red] {source_type!r}\n"
                f"Valid values: {', '.join(sorted(_DISPATCH))}"
            )
            raise typer.Exit(code=1)

        try:
            artifact = _DISPATCH[source_type](source_ref)
        except IngestNotFound as exc:
            err_console.print(f"[red]Not found:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except IngestUnauthorized as exc:
            err_console.print(f"[red]Unauthorized:[/red] {exc}")
            raise typer.Exit(code=1) from exc
        except IngestMalformed as exc:
            err_console.print(f"[red]Malformed payload:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{artifact.change_id}.json"
        output_path.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")

        console.print(
            Panel(
                f"[bold]change_id:[/bold] {artifact.change_id}\n"
                f"[bold]source_type:[/bold] {artifact.source_type}\n"
                f"[bold]source_ref:[/bold] {artifact.source_ref}\n"
                f"[bold]title:[/bold] {artifact.title}\n"
                f"[bold]output:[/bold] {output_path}",
                title="PulseCraft ingest",
                subtitle=source_ref,
            )
        )

        if not run:
            return

        from pulsecraft.orchestrator.audit import AuditWriter
        from pulsecraft.orchestrator.engine import Orchestrator
        from pulsecraft.orchestrator.hitl import HITLQueue
        from pulsecraft.orchestrator.mock_agents import MockBUAtlas, MockPushPilot, MockSignalScribe

        audit_writer = AuditWriter(root=audit_dir)
        hitl_queue = HITLQueue(audit_writer=audit_writer, root=queue_dir)
        orchestrator = Orchestrator(
            signalscribe=MockSignalScribe(),
            buatlas=MockBUAtlas(),
            pushpilot=MockPushPilot(),
            audit_writer=audit_writer,
            hitl_queue=hitl_queue,
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
                title="Pipeline result",
                subtitle=f"{result.audit_record_count} audit records written",
            )
        )

        if result.errors:
            for err in result.errors:
                err_console.print(f"[red]Error:[/red] {err}")

        raise typer.Exit(code=1 if str(result.terminal_state) == "FAILED" else 0)
