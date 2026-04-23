"""Unit tests for resolve_change_id helper."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
import typer

from pulsecraft.cli.common import resolve_change_id


def _seed_audit(tmp_path: Path, *change_ids: str) -> Path:
    """Write stub JSONL files so resolve_change_id can find them."""
    audit_dir = tmp_path / "audit"
    day_dir = audit_dir / "2026-04-23"
    day_dir.mkdir(parents=True, exist_ok=True)
    for cid in change_ids:
        (day_dir / f"{cid}.jsonl").write_text('{"stub": true}\n', encoding="utf-8")
    return audit_dir


class TestResolveChangeId:
    def test_full_uuid_returned_as_is(self, tmp_path: Path) -> None:
        full = str(uuid.uuid4())
        # Full UUIDs bypass the scan — no audit files needed
        result = resolve_change_id(full, tmp_path / "nonexistent_audit")
        assert result == full

    def test_prefix_resolves_to_full_uuid(self, tmp_path: Path) -> None:
        full = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        audit_dir = _seed_audit(tmp_path, full)
        result = resolve_change_id("a1b2c3d4", audit_dir)
        assert result == full

    def test_no_match_exits_with_code_2(self, tmp_path: Path) -> None:
        full = "aaaaaaaa-0000-0000-0000-000000000001"
        audit_dir = _seed_audit(tmp_path, full)
        with pytest.raises(typer.Exit) as exc_info:
            resolve_change_id("zzzzzzzz", audit_dir)
        assert exc_info.value.exit_code == 2

    def test_ambiguous_prefix_exits_with_code_2(self, tmp_path: Path) -> None:
        id_a = "abcdef01-0000-0000-0000-000000000001"
        id_b = "abcdef02-0000-0000-0000-000000000002"
        audit_dir = _seed_audit(tmp_path, id_a, id_b)
        with pytest.raises(typer.Exit) as exc_info:
            resolve_change_id("abcdef0", audit_dir)
        assert exc_info.value.exit_code == 2

    def test_missing_audit_dir_exits_with_code_2(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit) as exc_info:
            resolve_change_id("abcdef01", tmp_path / "no_such_dir")
        assert exc_info.value.exit_code == 2

    def test_prefix_too_short_exits_with_code_2(self, tmp_path: Path) -> None:
        audit_dir = _seed_audit(tmp_path, "abc00000-0000-0000-0000-000000000001")
        with pytest.raises(typer.Exit) as exc_info:
            resolve_change_id("ab", audit_dir)
        assert exc_info.value.exit_code == 2

    def test_longer_prefix_still_resolves(self, tmp_path: Path) -> None:
        full = "deadbeef-cafe-babe-feed-face00000000"
        audit_dir = _seed_audit(tmp_path, full)
        result = resolve_change_id("deadbeef-cafe", audit_dir)
        assert result == full
