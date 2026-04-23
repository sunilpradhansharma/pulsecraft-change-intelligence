"""Integration tests for the explain command output structure."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from pulsecraft.cli.main import app

runner = CliRunner()

FIXTURE_001 = Path("fixtures/changes/change_001_clearcut_communicate.json")


@pytest.fixture()
def pipeline_run(tmp_path: Path):
    """Run fixture 001 and return audit/queue dirs + change_id."""
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
    assert result.exit_code in (0, 1)

    change_id: str | None = None
    if audit_dir.exists():
        for day_dir in audit_dir.iterdir():
            if day_dir.is_dir():
                for p in day_dir.glob("*.jsonl"):
                    change_id = p.stem
                    break

    return {"audit_dir": audit_dir, "queue_dir": queue_dir, "change_id": change_id}


class TestExplainOutput:
    def test_explain_shows_pipeline_trace(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "Pipeline trace" in result.output

    def test_explain_shows_signalscribe_gates(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "SignalScribe" in result.output
        assert "COMMUNICATE" in result.output

    def test_explain_shows_buatlas_decision(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "BUAtlas" in result.output

    def test_explain_shows_state_journey(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "RECEIVED" in result.output

    def test_explain_shows_terminal_state(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        # Terminal state should appear — DELIVERED or AWAITING_HITL for fixture 001
        assert any(
            s in result.output
            for s in ["DELIVERED", "AWAITING_HITL", "HELD", "ARCHIVED", "DIGESTED"]
        )

    def test_explain_verbose_shows_policy_checks(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
                "--verbose",
            ],
        )
        assert result.exit_code == 0
        assert "Policy checks" in result.output

    def test_explain_no_draft_skips_delivery_block(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
                "--no-draft",
            ],
        )
        assert result.exit_code == 0
        # HITL and delivery sections should be absent
        assert "Awaiting review" not in result.output

    def test_explain_json_has_expected_fields(self, pipeline_run) -> None:
        import json

        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        for field in [
            "change_id",
            "terminal_state",
            "agent_decisions",
            "state_transitions",
            "invocation_count",
        ]:
            assert field in data, f"Missing field: {field}"

    def test_explain_totals_line_present(self, pipeline_run) -> None:
        cid = pipeline_run["change_id"]
        result = runner.invoke(
            app,
            [
                "explain",
                cid[:8],
                "--audit-dir",
                str(pipeline_run["audit_dir"]),
                "--queue-dir",
                str(pipeline_run["queue_dir"]),
            ],
        )
        assert result.exit_code == 0
        assert "invocation" in result.output.lower()

    def test_explain_unknown_change_id_exits_2(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / "empty_audit"
        audit_dir.mkdir()
        result = runner.invoke(
            app,
            [
                "explain",
                "zzzzzzzz",
                "--audit-dir",
                str(audit_dir),
            ],
        )
        assert result.exit_code == 2
