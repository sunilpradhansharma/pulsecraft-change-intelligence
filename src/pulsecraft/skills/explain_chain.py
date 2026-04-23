"""explain_chain skill — reconstruct a narrative explanation of a change's pipeline journey."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from pulsecraft.orchestrator.audit import AuditReader
from pulsecraft.schemas.audit_record import AuditDecision, AuditRecord, EventType


@dataclass
class AgentDecisionEvent:
    timestamp: datetime
    agent: str
    gate: int
    verb: str
    reason: str
    bu_id: str | None  # None for SignalScribe (applies globally)
    extra_verbs: list[tuple[int, str]]  # [(gate, verb)] for multi-gate agents beyond primary


@dataclass
class PolicyEvent:
    timestamp: datetime
    check_name: str
    passed: bool
    summary: str


@dataclass
class HITLEvent:
    timestamp: datetime
    action: str
    actor: str
    notes: str | None


@dataclass
class DeliveryEvent:
    timestamp: datetime
    bu_id: str
    decision: str
    channel: str
    reason: str


@dataclass
class StateTransitionEvent:
    timestamp: datetime
    from_state: str | None
    to_state: str
    reason: str


@dataclass
class Explanation:
    change_id: str
    terminal_state: str | None
    first_record_at: datetime | None
    last_record_at: datetime | None
    agent_decisions: list[AgentDecisionEvent] = field(default_factory=list)
    policy_events: list[PolicyEvent] = field(default_factory=list)
    hitl_events: list[HITLEvent] = field(default_factory=list)
    delivery_events: list[DeliveryEvent] = field(default_factory=list)
    state_transitions: list[StateTransitionEvent] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_seconds: float = 0.0
    invocation_count: int = 0
    errors: list[str] = field(default_factory=list)


def build_explanation(change_id: str, audit_reader: AuditReader) -> Explanation:
    """Reconstruct a narrative explanation of a change's journey through the pipeline.

    Reads the full audit chain and classifies each record into typed events. Returns
    an Explanation dataclass ready for rendering by the explain CLI command.
    """
    records = audit_reader.read_chain(change_id)

    if not records:
        return Explanation(
            change_id=change_id,
            terminal_state=None,
            first_record_at=None,
            last_record_at=None,
        )

    explanation = Explanation(
        change_id=change_id,
        terminal_state=None,
        first_record_at=records[0].timestamp,
        last_record_at=records[-1].timestamp,
    )

    total_cost = 0.0
    invocation_count = 0

    for record in records:
        if record.event_type == EventType.STATE_TRANSITION:
            _process_state_transition(record, explanation)
        elif record.event_type == EventType.AGENT_INVOCATION:
            _process_agent_invocation(record, explanation)
            invocation_count += 1
            if record.metrics and record.metrics.cost_usd:
                total_cost += record.metrics.cost_usd
        elif record.event_type == EventType.POLICY_CHECK:
            _process_policy_check(record, explanation)
        elif record.event_type == EventType.HITL_ACTION:
            _process_hitl_action(record, explanation)
        elif record.event_type == EventType.DELIVERY_ATTEMPT:
            _process_delivery_attempt(record, explanation)
        elif record.event_type == EventType.ERROR:
            explanation.errors.append(record.output_summary)

    explanation.total_cost_usd = total_cost
    explanation.invocation_count = invocation_count

    if explanation.first_record_at and explanation.last_record_at:
        delta = explanation.last_record_at - explanation.first_record_at
        explanation.total_latency_seconds = delta.total_seconds()

    # Terminal state = to_state of the last STATE_TRANSITION record
    if explanation.state_transitions:
        explanation.terminal_state = explanation.state_transitions[-1].to_state

    return explanation


# ── record processors ─────────────────────────────────────────────────────────


def _process_state_transition(record: AuditRecord, exp: Explanation) -> None:
    summary = record.output_summary
    # Format: "{from_state} → {to_state}: {reason}"
    arrow = " → "
    if arrow in summary:
        parts = summary.split(arrow, 1)
        from_state_str = parts[0].strip()
        rest = parts[1]
        if ": " in rest:
            to_state_str, reason = rest.split(": ", 1)
        else:
            to_state_str, reason = rest, ""
        from_state: str | None = None if from_state_str.lower() == "none" else from_state_str
        exp.state_transitions.append(
            StateTransitionEvent(
                timestamp=record.timestamp,
                from_state=from_state,
                to_state=to_state_str.strip(),
                reason=reason.strip(),
            )
        )


def _process_agent_invocation(record: AuditRecord, exp: Explanation) -> None:
    agent_raw = record.actor.id  # e.g. "signalscribe_mock", "buatlas_mock", "pushpilot"
    agent = agent_raw.replace("_mock", "")

    primary: AuditDecision | None = record.decision
    summary = record.output_summary
    extra_verbs: list[tuple[int, str]] = []

    if agent == "signalscribe":
        gate = primary.gate if primary else 1
        verb = primary.verb if primary else "?"
        reason = primary.reason if primary else ""
        extra_verbs = _parse_signalscribe_extra_verbs(summary)
        exp.agent_decisions.append(
            AgentDecisionEvent(
                timestamp=record.timestamp,
                agent=agent,
                gate=gate,
                verb=verb,
                reason=reason,
                bu_id=None,
                extra_verbs=extra_verbs,
            )
        )
    elif agent == "buatlas":
        bu_id = _extract_kv(summary, "bu") or _extract_kv(summary, "bu_id")
        gate = primary.gate if primary else 4
        verb = primary.verb if primary else "?"
        reason = primary.reason if primary else ""
        extra_verbs = _parse_buatlas_extra_verbs(summary)
        exp.agent_decisions.append(
            AgentDecisionEvent(
                timestamp=record.timestamp,
                agent=agent,
                gate=gate,
                verb=verb,
                reason=reason,
                bu_id=bu_id,
                extra_verbs=extra_verbs,
            )
        )
    elif agent == "pushpilot":
        bu_id = _extract_kv(summary, "bu") or _extract_kv(summary, "bu_id")
        gate = primary.gate if primary else 6
        verb = primary.verb if primary else "?"
        reason = primary.reason if primary else ""
        exp.agent_decisions.append(
            AgentDecisionEvent(
                timestamp=record.timestamp,
                agent=agent,
                gate=gate,
                verb=verb,
                reason=reason,
                bu_id=bu_id,
                extra_verbs=[],
            )
        )


def _process_policy_check(record: AuditRecord, exp: Explanation) -> None:
    summary = record.output_summary
    passed = summary.upper().startswith("PASSED")
    exp.policy_events.append(
        PolicyEvent(
            timestamp=record.timestamp,
            check_name=record.action,
            passed=passed,
            summary=summary,
        )
    )


def _process_hitl_action(record: AuditRecord, exp: Explanation) -> None:
    exp.hitl_events.append(
        HITLEvent(
            timestamp=record.timestamp,
            action=record.action,
            actor=record.actor.id,
            notes=record.output_summary,
        )
    )


def _process_delivery_attempt(record: AuditRecord, exp: Explanation) -> None:
    summary = record.output_summary
    # Format: "bu_id=X decision=Y channel=Z: reason"
    bu_id = _extract_kv(summary, "bu_id") or "?"
    decision = _extract_kv(summary, "decision") or "?"
    channel = _extract_kv(summary, "channel") or "?"
    reason = ""
    if ": " in summary:
        reason = summary.split(": ", 1)[1]
    exp.delivery_events.append(
        DeliveryEvent(
            timestamp=record.timestamp,
            bu_id=bu_id,
            decision=decision,
            channel=channel,
            reason=reason,
        )
    )


# ── parsing helpers ───────────────────────────────────────────────────────────


def _extract_kv(text: str, key: str) -> str | None:
    """Extract value from 'key=value' in text (stops at space or colon)."""
    m = re.search(rf"\b{re.escape(key)}=([^\s:]+)", text)
    return m.group(1) if m else None


def _parse_signalscribe_extra_verbs(output_summary: str) -> list[tuple[int, str]]:
    """Parse additional gate verbs from SignalScribe output_summary.

    Format: "brief_id=<uuid> decisions=['COMMUNICATE', 'RIPE', 'READY']"
    Returns [(2, 'RIPE'), (3, 'READY')] — gates 2+ beyond the primary gate 1.
    """
    m = re.search(r"decisions=\[([^\]]+)\]", output_summary)
    if not m:
        return []
    verbs_str = m.group(1)
    verbs = [v.strip().strip("'\"") for v in verbs_str.split(",")]
    # Index 0 = gate 1 (primary, already stored), 1 = gate 2, 2 = gate 3
    return [(i + 1, v) for i, v in enumerate(verbs) if i > 0]


def _parse_buatlas_extra_verbs(output_summary: str) -> list[tuple[int, str]]:
    """Infer gate 5 verb from BUAtlas output_summary quality field.

    Format: "bu=bu_alpha relevance=affected quality=worth_sending"
    """
    quality = _extract_kv(output_summary, "quality")
    if not quality or quality.lower() == "none":
        return []
    verb = quality.upper()
    return [(5, verb)]
