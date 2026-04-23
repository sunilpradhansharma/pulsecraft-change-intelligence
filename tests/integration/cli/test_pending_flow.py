"""Integration test for the pending → approve / reject flow."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from pulsecraft.cli.main import app

runner = CliRunner()


def _seed_hitl_item(queue_dir: Path, change_id: str, reason: str = "priority_p0") -> None:
    """Write a minimal HITL pending item directly to the queue."""
    pending_dir = queue_dir / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("approved", "rejected", "archived"):
        (queue_dir / sub).mkdir(exist_ok=True)

    data = {
        "change_id": change_id,
        "reason": reason,
        "status": "pending",
        "enqueued_at": datetime.now(UTC).isoformat(),
        "payload": {"brief_id": str(uuid.uuid4()), "reason": reason},
        "reviewer": None,
        "reviewer_notes": None,
    }
    (pending_dir / f"{change_id}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _seed_audit_for_id(audit_dir: Path, change_id: str) -> None:
    """Write a minimal audit JSONL so resolve_change_id can find the change_id."""
    import hashlib

    from pulsecraft.schemas.audit_record import (
        Actor,
        ActorType,
        AuditOutcome,
        AuditRecord,
        EventType,
    )

    day_dir = audit_dir / "2026-04-23"
    day_dir.mkdir(parents=True, exist_ok=True)
    record = AuditRecord(
        audit_id=str(uuid.uuid4()),
        timestamp=datetime.now(UTC),
        event_type=EventType.STATE_TRANSITION,
        change_id=change_id,
        actor=Actor(type=ActorType.ORCHESTRATOR, id="orchestrator", version="1.0"),
        action="transition",
        input_hash=hashlib.sha256(change_id.encode()).hexdigest(),
        output_summary="None → RECEIVED: test",
        outcome=AuditOutcome.SUCCESS,
    )
    path = day_dir / f"{change_id}.jsonl"
    path.write_text(record.model_dump_json() + "\n", encoding="utf-8")


class TestPendingApproveFlow:
    def test_pending_shows_seeded_item(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_hitl_item(queue_dir, change_id)
        _seed_audit_for_id(audit_dir, change_id)

        result = runner.invoke(
            app,
            [
                "pending",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        assert change_id[:8] in result.output

    def test_approve_moves_to_approved(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_hitl_item(queue_dir, change_id)
        _seed_audit_for_id(audit_dir, change_id)

        result = runner.invoke(
            app,
            [
                "approve",
                change_id[:8],
                "--reviewer",
                "test-operator",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Approved" in result.output

        # Verify file moved
        assert not (queue_dir / "pending" / f"{change_id}.json").exists()
        assert (queue_dir / "approved" / f"{change_id}.json").exists()

    def test_pending_empty_after_approve(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_hitl_item(queue_dir, change_id)
        _seed_audit_for_id(audit_dir, change_id)

        runner.invoke(
            app,
            [
                "approve",
                change_id,
                "--reviewer",
                "test-operator",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )

        result = runner.invoke(
            app,
            [
                "pending",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        # Item gone from pending list
        assert change_id[:8] not in result.output

    def test_reject_moves_to_rejected(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_hitl_item(queue_dir, change_id)
        _seed_audit_for_id(audit_dir, change_id)

        result = runner.invoke(
            app,
            [
                "reject",
                change_id,
                "--reason",
                "Not actionable for this BU",
                "--reviewer",
                "test-operator",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        assert "Rejected" in result.output
        assert (queue_dir / "rejected" / f"{change_id}.json").exists()

    def test_approve_not_pending_exits_2(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_audit_for_id(audit_dir, change_id)
        # Do NOT seed a pending item
        for sub in ("pending", "approved", "rejected", "archived"):
            (queue_dir / sub).mkdir(parents=True, exist_ok=True)

        result = runner.invoke(
            app,
            [
                "approve",
                change_id,
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 2

    def test_approve_json_output(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_hitl_item(queue_dir, change_id)
        _seed_audit_for_id(audit_dir, change_id)

        result = runner.invoke(
            app,
            [
                "approve",
                change_id,
                "--reviewer",
                "op",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["action"] == "approved"
        assert parsed["change_id"] == change_id

    def test_edit_records_in_queue(self, tmp_path: Path) -> None:
        change_id = str(uuid.uuid4())
        queue_dir = tmp_path / "queue" / "hitl"
        audit_dir = tmp_path / "audit"
        _seed_hitl_item(queue_dir, change_id)
        _seed_audit_for_id(audit_dir, change_id)

        result = runner.invoke(
            app,
            [
                "edit",
                change_id,
                "--field",
                "message_variants.teams_medium",
                "--value",
                "Updated message text.",
                "--reviewer",
                "op",
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        # Check edit was recorded in the pending file
        data = json.loads((queue_dir / "pending" / f"{change_id}.json").read_text())
        assert "edits" in data
        assert data["edits"][0]["field_path"] == "message_variants.teams_medium"
