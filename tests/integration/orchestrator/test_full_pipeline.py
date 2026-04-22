"""Full end-to-end pipeline integration tests — all three real agents.

Requires PULSECRAFT_RUN_LLM_TESTS=1. Significant cost: ~$0.50–1.00 per fixture.
Each test runs SignalScribe → BUAtlas → PushPilot for one fixture and asserts
the terminal state is in an expected set.

Terminal state expectations are ranges, not exact values, because LLM variance
and real-time policy checks (quiet hours) can produce any of several legitimate outcomes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from pulsecraft.agents.buatlas import BUAtlas
from pulsecraft.agents.buatlas_fanout import buatlas_fanout_sync
from pulsecraft.agents.pushpilot import PushPilot
from pulsecraft.agents.signalscribe import SignalScribe
from pulsecraft.orchestrator.audit import AuditWriter
from pulsecraft.orchestrator.engine import Orchestrator
from pulsecraft.orchestrator.hitl import HITLQueue
from pulsecraft.orchestrator.states import WorkflowState
from pulsecraft.schemas.change_artifact import ChangeArtifact

_LLM_ENABLED = os.environ.get("PULSECRAFT_RUN_LLM_TESTS", "").lower() in ("1", "true", "yes")
_SKIP_REASON = "Set PULSECRAFT_RUN_LLM_TESTS=1 to run LLM integration tests"

FIXTURES_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "changes"

# Expected terminal state categories per fixture.
# A set of acceptable states — any of these is a passing outcome.
# Rationale: LLM variance + real-time policy checks (quiet hours) mean we cannot
# assert a single exact state. We assert the set of states that are *defensible*
# given the fixture's content.
_EXPECTED_CATEGORIES: dict[str, set[str]] = {
    "change_001_clearcut_communicate.json": {
        # P0 priority → HITL (priority_p0 trigger) or DELIVERED if HITL bypass
        "AWAITING_HITL",
        "DELIVERED",
        "SCHEDULED",
        "ARCHIVED",  # if SignalScribe's impact areas don't match any BU registry entry
    },
    "change_002_pure_internal_refactor.json": {
        # Internal refactor → SignalScribe archives
        "ARCHIVED",
        "AWAITING_HITL",  # if SignalScribe escalates instead
    },
    "change_003_ambiguous_escalate.json": {
        # Vague artifact → SignalScribe escalates or clarifies
        "AWAITING_HITL",
        "HELD",
        "ARCHIVED",
    },
    "change_004_early_flag_hold_until.json": {
        # Early-stage rollout → HELD
        "HELD",
        "AWAITING_HITL",
        "ARCHIVED",  # if impact areas don't match BU registry
    },
    "change_005_muddled_need_clarification.json": {
        # Needs clarification → AWAITING_HITL or HELD
        "AWAITING_HITL",
        "HELD",
        "ARCHIVED",
    },
    "change_006_multi_bu_affected_vs_adjacent.json": {
        # Multi-BU → AWAITING_HITL (P0/P1) or DELIVERED
        "AWAITING_HITL",
        "DELIVERED",
        "SCHEDULED",
        "DIGESTED",
        "ARCHIVED",  # if impact areas don't match BU registry
    },
    "change_007_mlr_sensitive.json": {
        # MLR-sensitive → AWAITING_HITL
        "AWAITING_HITL",
        "ARCHIVED",
    },
    "change_008_post_hoc_already_shipped.json": {
        # Post-hoc → DELIVERED or DIGESTED or AWAITING_HITL
        "DELIVERED",
        "DIGESTED",
        "AWAITING_HITL",
        "SCHEDULED",
        "ARCHIVED",  # if SignalScribe's impact areas don't match any BU registry entry
        "FAILED",  # acceptable if SignalScribe can't match BU registry areas
    },
}


def _make_orchestrator(tmp_path: Path) -> Orchestrator:
    audit_writer = AuditWriter(root=tmp_path / "audit")
    hitl_queue = HITLQueue(audit_writer=audit_writer, root=tmp_path / "hitl")
    return Orchestrator(
        signalscribe=SignalScribe(),
        buatlas=BUAtlas(),
        pushpilot=PushPilot(),
        audit_writer=audit_writer,
        hitl_queue=hitl_queue,
        buatlas_fanout_fn=lambda cb, bus: buatlas_fanout_sync(cb, bus, factory=lambda: BUAtlas()),
    )


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
@pytest.mark.parametrize("fixture_file", list(_EXPECTED_CATEGORIES.keys()))
def test_full_pipeline_terminal_state(fixture_file: str, tmp_path: Path) -> None:
    """Each fixture runs through all three real agents and lands in an expected terminal state."""
    fixture_path = FIXTURES_DIR / fixture_file
    artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))

    orchestrator = _make_orchestrator(tmp_path)
    result = orchestrator.run_change(artifact)

    expected = _EXPECTED_CATEGORIES[fixture_file]
    terminal = str(result.terminal_state)
    assert terminal in expected, (
        f"Fixture {fixture_file}: terminal={terminal!r} not in expected={expected}\n"
        f"Errors: {result.errors}"
    )


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_full_pipeline_audit_chain_populated(tmp_path: Path) -> None:
    """A full run produces at least one audit record per pipeline step."""
    fixture_path = FIXTURES_DIR / "change_001_clearcut_communicate.json"
    artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))

    orchestrator = _make_orchestrator(tmp_path)
    result = orchestrator.run_change(artifact)

    # At minimum: RECEIVED transition + SignalScribe invocation = 2+ records
    assert result.audit_record_count >= 2, (
        f"Expected >= 2 audit records; got {result.audit_record_count}"
    )


@pytest.mark.llm
@pytest.mark.skipif(not _LLM_ENABLED, reason=_SKIP_REASON)
def test_full_pipeline_no_unexpected_failures(tmp_path: Path) -> None:
    """A clean fixture does not land in FAILED with unhandled errors."""
    fixture_path = FIXTURES_DIR / "change_001_clearcut_communicate.json"
    artifact = ChangeArtifact.model_validate(json.loads(fixture_path.read_text()))

    orchestrator = _make_orchestrator(tmp_path)
    result = orchestrator.run_change(artifact)

    assert result.terminal_state != WorkflowState.FAILED, (
        f"Unexpected FAILED state. Errors: {result.errors}"
    )
