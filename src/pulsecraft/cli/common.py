"""Shared CLI utilities: change_id resolution, formatting, infrastructure loaders."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pulsecraft.orchestrator.audit import AuditWriter
    from pulsecraft.orchestrator.hitl import HITLQueue

import typer
from rich.console import Console

err_console = Console(stderr=True)

_AUDIT_ENV = "PULSECRAFT_AUDIT_DIR"
_QUEUE_ENV = "PULSECRAFT_QUEUE_DIR"

DEFAULT_AUDIT_DIR = Path("audit")
DEFAULT_QUEUE_DIR = Path("queue/hitl")


def resolve_change_id(prefix: str, audit_dir: Path = DEFAULT_AUDIT_DIR) -> str:
    """Resolve a partial change_id prefix (≥8 chars) to a full UUID.

    Scans audit/<YYYY-MM-DD>/<change_id>.jsonl filenames. Accepts the full UUID
    as-is. Raises typer.Exit(2) on no match or ambiguous match.
    """
    # Full UUID shortcut
    if len(prefix) == 36 and prefix.count("-") >= 4:
        return prefix

    if len(prefix) < 4:
        err_console.print(
            f"[red]change_id prefix too short:[/red] {prefix!r} — provide at least 4 characters"
        )
        raise typer.Exit(code=2)

    matches: set[str] = set()
    if not audit_dir.exists():
        err_console.print(
            f"[red]No audit records found.[/red] (audit_dir={audit_dir} does not exist)"
        )
        raise typer.Exit(code=2)

    for day_dir in audit_dir.iterdir():
        if not day_dir.is_dir():
            continue
        for p in day_dir.glob("*.jsonl"):
            change_id = p.stem
            if change_id.startswith(prefix):
                matches.add(change_id)

    if not matches:
        err_console.print(
            f"[red]No change_id found matching prefix:[/red] {prefix!r}\n"
            f"Run [bold]pulsecraft audit --list[/bold] to see available change_ids."
        )
        raise typer.Exit(code=2)

    if len(matches) > 1:
        listed = ", ".join(sorted(matches)[:5])
        err_console.print(
            f"[red]Ambiguous prefix:[/red] {prefix!r} matches {len(matches)} change_ids: {listed}"
        )
        raise typer.Exit(code=2)

    return next(iter(matches))


def get_audit_dir(option: Path | None = None) -> Path:
    """Return the effective audit directory, respecting env override."""
    if option is not None:
        return option
    return Path(os.environ.get(_AUDIT_ENV, str(DEFAULT_AUDIT_DIR)))


def get_queue_dir(option: Path | None = None) -> Path:
    """Return the effective HITL queue directory, respecting env override."""
    if option is not None:
        return option
    return Path(os.environ.get(_QUEUE_ENV, str(DEFAULT_QUEUE_DIR)))


def load_audit_writer(audit_dir: Path) -> AuditWriter:
    from pulsecraft.orchestrator.audit import AuditWriter

    return AuditWriter(root=audit_dir)


def load_hitl_queue(queue_dir: Path, audit_dir: Path) -> HITLQueue:
    from pulsecraft.orchestrator.hitl import HITLQueue

    return HITLQueue(audit_writer=load_audit_writer(audit_dir), root=queue_dir)


def format_ts(ts: datetime) -> str:
    """Format a datetime as HH:MM:SS for display."""
    return ts.strftime("%H:%M:%S")


def format_date(ts: datetime) -> str:
    """Format a datetime as YYYY-MM-DD HH:MM:SS UTC."""
    return ts.strftime("%Y-%m-%d %H:%M:%S UTC")


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def print_json_output(obj: Any, console: Console | None = None) -> None:
    """Serialize obj to JSON and print. Handles dataclasses and Pydantic models."""
    import dataclasses

    from pydantic import BaseModel

    if console is None:
        console = Console()

    if isinstance(obj, BaseModel):
        console.print_json(obj.model_dump_json(indent=2))
    elif dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        console.print_json(json.dumps(dataclasses.asdict(obj), default=_json_default, indent=2))
    elif isinstance(obj, list):
        serialized = []
        for item in obj:
            if isinstance(item, BaseModel):
                serialized.append(item.model_dump())
            elif dataclasses.is_dataclass(item) and not isinstance(item, type):
                serialized.append(dataclasses.asdict(item))
            else:
                serialized.append(item)
        console.print_json(json.dumps(serialized, default=_json_default, indent=2))
    else:
        console.print_json(json.dumps(obj, default=_json_default, indent=2))


def _json_default(obj: Any) -> Any:
    from datetime import datetime

    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def reviewer_from_env() -> str:
    """Return the operator name from USER/USERNAME env, or 'operator'."""
    return os.environ.get("USER") or os.environ.get("USERNAME") or "operator"
