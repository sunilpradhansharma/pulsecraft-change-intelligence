"""Smoke tests — each command exits 0 and produces some output."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulsecraft.cli.main import app

runner = CliRunner()

FIXTURE_001 = Path("fixtures/changes/change_001_clearcut_communicate.json")


@pytest.fixture()
def seeded_env(tmp_path: Path):
    """Run fixture 001 through the pipeline and return the audit/queue dirs."""
    audit_dir = tmp_path / "audit"
    queue_dir = tmp_path / "queue" / "hitl"
    result = runner.invoke(
        app,
        [
            "run-change",
            str(FIXTURE_001),
            "--audit-dir",
            str(audit_dir),
            "--queue-dir",
            str(queue_dir),
        ],
    )
    assert result.exit_code in (0, 1)  # DELIVERED=0, AWAITING_HITL also ok
    # Return the change_id from the written audit files
    change_id: str | None = None
    if audit_dir.exists():
        for day_dir in audit_dir.iterdir():
            if day_dir.is_dir():
                for p in day_dir.glob("*.jsonl"):
                    change_id = p.stem
                    break
    return {
        "audit_dir": audit_dir,
        "queue_dir": queue_dir,
        "change_id": change_id,
    }


class TestCommandsSmoke:
    def test_help_exits_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "pulsecraft" in result.output.lower()

    def test_run_change_smoke(self) -> None:
        result = runner.invoke(app, ["run-change", str(FIXTURE_001)])
        assert result.exit_code in (0, 1)
        assert "change_id" in result.output.lower() or len(result.output) > 20

    def test_dryrun_smoke(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / "audit"
        queue_dir = tmp_path / "queue" / "hitl"
        result = runner.invoke(
            app,
            [
                "dryrun",
                str(FIXTURE_001),
                "--audit-dir",
                str(audit_dir),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        assert "DRYRUN" in result.output

    def test_pending_empty(self, tmp_path: Path) -> None:
        queue_dir = tmp_path / "queue" / "hitl"
        queue_dir.mkdir(parents=True, exist_ok=True)
        (queue_dir / "pending").mkdir(exist_ok=True)
        result = runner.invoke(
            app,
            [
                "pending",
                "--audit-dir",
                str(tmp_path / "audit"),
                "--queue-dir",
                str(queue_dir),
            ],
        )
        assert result.exit_code == 0
        assert "pending" in result.output.lower() or "No pending" in result.output

    def test_digest_no_scheduled(self, tmp_path: Path) -> None:
        queue_dir = tmp_path / "queue" / "hitl"
        queue_dir.mkdir(parents=True, exist_ok=True)
        result = runner.invoke(app, ["digest", "--queue-dir", str(queue_dir)])
        assert result.exit_code == 0

    def test_metrics_no_data(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["metrics", "--audit-dir", str(tmp_path / "audit")])
        assert result.exit_code == 0

    def test_audit_list(self, seeded_env) -> None:
        result = runner.invoke(
            app,
            [
                "audit",
                "placeholder",
                "--audit-dir",
                str(seeded_env["audit_dir"]),
                "--list",
            ],
        )
        assert result.exit_code == 0
        assert seeded_env["change_id"][:8] in result.output

    def test_audit_chain(self, seeded_env) -> None:
        cid = seeded_env["change_id"]
        result = runner.invoke(
            app,
            [
                "audit",
                cid[:8],
                "--audit-dir",
                str(seeded_env["audit_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "Audit chain" in result.output and len(result.output) > 100

    def test_explain_smoke(self, seeded_env) -> None:
        cid = seeded_env["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(seeded_env["audit_dir"]),
                "--queue-dir",
                str(seeded_env["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "Pipeline trace" in result.output

    def test_explain_json(self, seeded_env) -> None:
        cid = seeded_env["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(seeded_env["audit_dir"]),
                "--queue-dir",
                str(seeded_env["queue_dir"]),
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "change_id" in parsed
        assert parsed["change_id"] == cid

    def test_metrics_json(self, seeded_env) -> None:
        result = runner.invoke(
            app,
            [
                "metrics",
                "--audit-dir",
                str(seeded_env["audit_dir"]),
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "changes_in_window" in parsed
        assert parsed["changes_in_window"] >= 1

    def test_pending_json(self, seeded_env) -> None:
        result = runner.invoke(
            app,
            [
                "pending",
                "--audit-dir",
                str(seeded_env["audit_dir"]),
                "--queue-dir",
                str(seeded_env["queue_dir"]),
                "--json",
            ],
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert isinstance(parsed, list)
