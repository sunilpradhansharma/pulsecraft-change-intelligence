"""answer command — provide answers to gate-3 clarification questions."""

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
    @app.command("answer")
    def answer(
        change_id: str = typer.Argument(  # noqa: B008
            ...,
            help="change_id (full UUID or first 8 chars) of the pending HITL item.",
        ),
        answers: list[str] | None = typer.Option(  # noqa: B008
            None,
            "--answer",
            help="key=value pair (repeatable). E.g. --answer rollout_date=2026-05-01.",
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
        """Provide answers to gate-3 clarification questions.

        Use --answer key=value (repeatable) to supply answers. If none are
        provided, lists the open questions from the pending item.

        V1: records answers in audit. SignalScribe re-invocation with answers
        is handled in a future prompt.
        """
        from pulsecraft.cli.common import load_hitl_queue

        full_id = resolve_change_id(change_id, audit_dir)
        reviewer_name = reviewer or reviewer_from_env()
        queue = load_hitl_queue(queue_dir, audit_dir)

        if not queue.is_pending(full_id):
            err_console.print(f"[red]Not found in pending queue:[/red] {full_id}")
            raise typer.Exit(code=2)

        # If no answers provided, show open questions from the pending payload
        if not answers:
            import json

            pending_path = queue._path("pending", full_id)
            data = json.loads(pending_path.read_text(encoding="utf-8"))
            payload = data.get("payload", {})
            questions = payload.get("open_questions") or []

            if questions:
                console.print(f"\n[bold]Open questions for {full_id[:8]}:[/bold]")
                for i, q in enumerate(questions, 1):
                    console.print(f"  {i}. {q}")
                console.print(
                    "\nProvide answers with: "
                    "[bold]pulsecraft answer <change-id> --answer q1=<answer1> --answer q2=<answer2>[/bold]"
                )
            else:
                console.print(
                    f"[yellow]No open questions found in payload for {full_id[:8]}.[/yellow]\n"
                    "This item may not be a gate-3 clarification request."
                )
            return

        # Parse key=value pairs
        parsed: dict[str, str] = {}
        for pair in answers:
            if "=" not in pair:
                err_console.print(f"[red]Invalid --answer format:[/red] {pair!r} — use key=value")
                raise typer.Exit(code=1)
            k, _, v = pair.partition("=")
            parsed[k.strip()] = v.strip()

        try:
            queue.answer_clarification(full_id, answers=parsed, reviewer=reviewer_name)
        except Exception as exc:
            err_console.print(f"[red]Answer failed:[/red] {exc}")
            raise typer.Exit(code=1) from exc

        if output_json:
            from pulsecraft.cli.common import print_json_output

            print_json_output(
                {
                    "change_id": full_id,
                    "action": "answered",
                    "answers": parsed,
                    "reviewer": reviewer_name,
                }
            )
        else:
            console.print(
                Panel(
                    f"[cyan]Answered[/cyan]   {full_id}\n"
                    f"Answers:   {parsed}\n"
                    f"Reviewer:  {reviewer_name}\n\n"
                    "[dim]Answers recorded. SignalScribe re-invocation: future prompt.[/dim]",
                    title="Clarification answers recorded",
                )
            )
