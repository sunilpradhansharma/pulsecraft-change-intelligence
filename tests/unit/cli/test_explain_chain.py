"""Unit tests for the explain_chain skill."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pulsecraft.orchestrator.audit import AuditWriter
from pulsecraft.schemas.audit_record import (
    Actor,
    ActorType,
    AuditDecision,
    AuditOutcome,
    AuditRecord,
    EventType,
)
from pulsecraft.skills.explain_chain import build_explanation


def _ts(offset_seconds: float = 0.0) -> datetime:
    base = datetime(2026, 4, 23, 14, 41, 25, tzinfo=UTC)
    from datetime import timedelta

    return base + timedelta(seconds=offset_seconds)


def _orchestrator_actor() -> Actor:
    return Actor(type=ActorType.ORCHESTRATOR, id="orchestrator", version="1.0")


def _agent_actor(name: str) -> Actor:
    return Actor(type=ActorType.AGENT, id=name, version="mock-1.0")


def _human_actor(name: str = "hitl_queue") -> Actor:
    return Actor(type=ActorType.HUMAN, id=name, version=None)


def _make_record(
    change_id: str,
    event_type: EventType,
    actor: Actor,
    action: str,
    output_summary: str,
    decision: AuditDecision | None = None,
    timestamp_offset: float = 0.0,
) -> AuditRecord:
    import hashlib

    return AuditRecord(
        audit_id=str(uuid.uuid4()),
        timestamp=_ts(timestamp_offset),
        event_type=event_type,
        change_id=change_id,
        actor=actor,
        action=action,
        input_hash=hashlib.sha256(output_summary.encode()).hexdigest(),
        output_summary=output_summary,
        decision=decision,
        outcome=AuditOutcome.SUCCESS,
    )


def _seed_audit(tmp_path: Path, change_id: str, records: list[AuditRecord]) -> AuditWriter:
    writer = AuditWriter(root=tmp_path / "audit")
    for r in records:
        writer.log_event(r)
    return writer


class TestBuildExplanation:
    def test_empty_returns_empty_explanation(self, tmp_path: Path) -> None:
        writer = AuditWriter(root=tmp_path / "audit")
        exp = build_explanation("00000000-0000-0000-0000-000000000000", writer)
        assert exp.terminal_state is None
        assert exp.agent_decisions == []
        assert exp.state_transitions == []

    def test_terminal_state_from_last_transition(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                _orchestrator_actor(),
                "transition",
                "None → RECEIVED: artifact accepted",
                timestamp_offset=0,
            ),
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                _orchestrator_actor(),
                "transition",
                "RECEIVED → INTERPRETED: signalscribe event",
                timestamp_offset=1,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        assert exp.terminal_state == "INTERPRETED"

    def test_agent_decisions_extracted(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                _agent_actor("signalscribe_mock"),
                "invoked",
                f"brief_id={uuid.uuid4()} decisions=['COMMUNICATE', 'RIPE', 'READY']",
                decision=AuditDecision(gate=1, verb="COMMUNICATE", reason="visible change"),
                timestamp_offset=0.5,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        assert len(exp.agent_decisions) == 1
        ev = exp.agent_decisions[0]
        assert ev.agent == "signalscribe"
        assert ev.gate == 1
        assert ev.verb == "COMMUNICATE"
        assert ev.reason == "visible change"
        # Extra verbs: gates 2 and 3 parsed from output_summary
        assert len(ev.extra_verbs) == 2
        assert ev.extra_verbs[0] == (2, "RIPE")
        assert ev.extra_verbs[1] == (3, "READY")

    def test_buatlas_extra_verb_from_quality(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                _agent_actor("buatlas_mock"),
                "invoked",
                "bu=bu_alpha relevance=affected quality=worth_sending",
                decision=AuditDecision(gate=4, verb="AFFECTED", reason="owns specialty_pharmacy"),
                timestamp_offset=1,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        ev = exp.agent_decisions[0]
        assert ev.bu_id == "bu_alpha"
        assert ev.gate == 4
        assert ev.verb == "AFFECTED"
        assert len(ev.extra_verbs) == 1
        assert ev.extra_verbs[0] == (5, "WORTH_SENDING")

    def test_pushpilot_decision_extracted(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                _agent_actor("pushpilot_mock"),
                "invoked",
                "bu=bu_alpha decision=SEND_NOW channel=teams",
                decision=AuditDecision(gate=6, verb="SEND_NOW", reason="within working hours"),
                timestamp_offset=2,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        ev = exp.agent_decisions[0]
        assert ev.agent == "pushpilot"
        assert ev.gate == 6
        assert ev.verb == "SEND_NOW"
        assert ev.bu_id == "bu_alpha"
        assert ev.extra_verbs == []

    def test_hitl_events_extracted(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.HITL_ACTION,
                Actor(type=ActorType.ORCHESTRATOR, id="hitl_queue", version=None),
                "enqueued",
                "Enqueued for HITL review: reason=priority_p0",
                timestamp_offset=3,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        assert len(exp.hitl_events) == 1
        he = exp.hitl_events[0]
        assert he.action == "enqueued"
        assert "priority_p0" in he.notes

    def test_delivery_events_extracted(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.DELIVERY_ATTEMPT,
                _orchestrator_actor(),
                "deliver",
                "bu_id=bu_alpha decision=SEND_NOW channel=teams: mock reason",
                timestamp_offset=4,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        assert len(exp.delivery_events) == 1
        de = exp.delivery_events[0]
        assert de.bu_id == "bu_alpha"
        assert de.decision == "SEND_NOW"
        assert de.channel == "teams"
        assert "mock reason" in de.reason

    def test_latency_computed(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                _orchestrator_actor(),
                "transition",
                "None → RECEIVED: start",
                timestamp_offset=0,
            ),
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                _orchestrator_actor(),
                "transition",
                "RECEIVED → DELIVERED: done",
                timestamp_offset=10.5,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        assert abs(exp.total_latency_seconds - 10.5) < 0.1

    def test_invocation_count(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                _agent_actor("signalscribe_mock"),
                "invoked",
                f"brief_id={uuid.uuid4()} decisions=['COMMUNICATE', 'RIPE', 'READY']",
                decision=AuditDecision(gate=1, verb="COMMUNICATE", reason="test"),
                timestamp_offset=0,
            ),
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                _agent_actor("buatlas_mock"),
                "invoked",
                "bu=bu_alpha relevance=affected quality=worth_sending",
                decision=AuditDecision(gate=4, verb="AFFECTED", reason="test"),
                timestamp_offset=1,
            ),
        ]
        writer = _seed_audit(tmp_path, cid, records)
        exp = build_explanation(cid, writer)
        assert exp.invocation_count == 2

    def test_errors_collected(self, tmp_path: Path) -> None:
        from pulsecraft.schemas.audit_record import AuditError

        cid = str(uuid.uuid4())
        import hashlib

        r = AuditRecord(
            audit_id=str(uuid.uuid4()),
            timestamp=_ts(),
            event_type=EventType.ERROR,
            change_id=cid,
            actor=_orchestrator_actor(),
            action="error",
            input_hash=hashlib.sha256(b"err").hexdigest(),
            output_summary="UNEXPECTED_ERROR: something broke",
            outcome=AuditOutcome.FAILURE,
            error=AuditError(code="UNEXPECTED_ERROR", message="something broke"),
        )
        writer = _seed_audit(tmp_path, cid, [r])
        exp = build_explanation(cid, writer)
        assert len(exp.errors) == 1
        assert "UNEXPECTED_ERROR" in exp.errors[0]
