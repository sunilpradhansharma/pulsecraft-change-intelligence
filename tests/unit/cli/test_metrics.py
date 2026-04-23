"""Unit tests for metrics aggregation helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from pulsecraft.orchestrator.audit import AuditWriter
from pulsecraft.schemas.audit_record import (
    Actor,
    ActorType,
    AuditOutcome,
    AuditRecord,
    EventType,
)


def _ts(day: str = "2026-04-23", hour: int = 14, minute: int = 0) -> datetime:
    return datetime(2026, 4, int(day[-2:]), hour, minute, tzinfo=UTC)


def _make_record(
    change_id: str,
    event_type: EventType,
    actor_id: str,
    action: str,
    output_summary: str,
    ts: datetime | None = None,
) -> AuditRecord:
    import hashlib

    return AuditRecord(
        audit_id=str(uuid.uuid4()),
        timestamp=ts or _ts(),
        event_type=event_type,
        change_id=change_id,
        actor=Actor(type=ActorType.ORCHESTRATOR, id=actor_id, version=None),
        action=action,
        input_hash=hashlib.sha256(output_summary.encode()).hexdigest(),
        output_summary=output_summary,
        outcome=AuditOutcome.SUCCESS,
    )


def _seed(tmp_path: Path, change_id: str, records: list[AuditRecord]) -> AuditWriter:
    writer = AuditWriter(root=tmp_path / "audit")
    for r in records:
        writer.log_event(r)
    return writer


class TestMetricsAggregation:
    def test_delivery_count_per_bu(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.DELIVERY_ATTEMPT,
                "orchestrator",
                "deliver",
                "bu_id=bu_alpha decision=SEND_NOW channel=teams: ok",
            ),
            _make_record(
                cid,
                EventType.DELIVERY_ATTEMPT,
                "orchestrator",
                "deliver",
                "bu_id=bu_alpha decision=SEND_NOW channel=teams: ok",
            ),
            _make_record(
                cid,
                EventType.DELIVERY_ATTEMPT,
                "orchestrator",
                "deliver",
                "bu_id=bu_beta decision=SEND_NOW channel=email: ok",
            ),
        ]
        writer = _seed(tmp_path, cid, records)

        # Verify delivery records are queryable
        delivery_records = writer.read_recent_events(EventType.DELIVERY_ATTEMPT, window_hours=24)
        assert len(delivery_records) == 3

        alpha_count = sum(1 for r in delivery_records if "bu_id=bu_alpha" in r.output_summary)
        beta_count = sum(1 for r in delivery_records if "bu_id=bu_beta" in r.output_summary)
        assert alpha_count == 2
        assert beta_count == 1

    def test_terminal_state_from_last_transition(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                "orchestrator",
                "transition",
                "None → RECEIVED: start",
                ts=_ts(hour=14, minute=0),
            ),
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                "orchestrator",
                "transition",
                "RECEIVED → INTERPRETED: ok",
                ts=_ts(hour=14, minute=1),
            ),
            _make_record(
                cid,
                EventType.STATE_TRANSITION,
                "orchestrator",
                "transition",
                "INTERPRETED → DELIVERED: done",
                ts=_ts(hour=14, minute=2),
            ),
        ]
        writer = _seed(tmp_path, cid, records)
        chain = writer.read_chain(cid)
        # Last state_transition output_summary: "INTERPRETED → DELIVERED: done"
        st_records = [r for r in chain if r.event_type == EventType.STATE_TRANSITION]
        last = st_records[-1]
        assert "DELIVERED" in last.output_summary

    def test_hitl_reason_counted(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.HITL_ACTION,
                "hitl_queue",
                "enqueued",
                "Enqueued for HITL review: reason=priority_p0",
            ),
        ]
        writer = _seed(tmp_path, cid, records)
        hitl_records = writer.read_recent_events(EventType.HITL_ACTION, window_hours=24)
        assert len(hitl_records) == 1
        assert "priority_p0" in hitl_records[0].output_summary

    def test_agent_invocation_counted(self, tmp_path: Path) -> None:
        cid = str(uuid.uuid4())
        records = [
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                "signalscribe_mock",
                "invoked",
                "brief_id=abc decisions=['COMMUNICATE']",
            ),
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                "buatlas_mock",
                "invoked",
                "bu=bu_alpha relevance=affected quality=worth_sending",
            ),
            _make_record(
                cid,
                EventType.AGENT_INVOCATION,
                "pushpilot_mock",
                "invoked",
                "bu=bu_alpha decision=SEND_NOW channel=teams",
            ),
        ]
        writer = _seed(tmp_path, cid, records)
        inv_records = writer.read_recent_events(EventType.AGENT_INVOCATION, window_hours=24)
        assert len(inv_records) == 3
