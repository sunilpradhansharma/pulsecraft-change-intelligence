"""AuditRecord schema — append-only audit log entry."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

UUIDStr = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]


class EventType(StrEnum):
    """Categories of auditable events."""

    AGENT_INVOCATION = "agent_invocation"
    TOOL_CALL = "tool_call"
    HOOK_FIRED = "hook_fired"
    HITL_ACTION = "hitl_action"
    DELIVERY_ATTEMPT = "delivery_attempt"
    STATE_TRANSITION = "state_transition"
    POLICY_CHECK = "policy_check"
    ERROR = "error"


class ActorType(StrEnum):
    """Types of actors that can appear in an audit record."""

    AGENT = "agent"
    ORCHESTRATOR = "orchestrator"
    SKILL = "skill"
    HOOK = "hook"
    HUMAN = "human"


class AuditOutcome(StrEnum):
    """Final outcome of an audited event."""

    SUCCESS = "success"
    FAILURE = "failure"
    RETRY_SCHEDULED = "retry_scheduled"
    ESCALATED = "escalated"


class Actor(BaseModel):
    """The component or person that triggered an audited event."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    type: ActorType
    id: str = Field(
        description="Stable actor identifier (e.g., 'signalscribe', 'pre-delivery-hook'). "
        "Must not be an email address."
    )
    version: str | None = Field(default=None, description="Component version, if applicable.")


class CorrelationIds(BaseModel):
    """Optional cross-record correlation identifiers."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    brief_id: UUIDStr | None = None
    personalized_brief_id: UUIDStr | None = None
    delivery_id: UUIDStr | None = None
    invocation_id: UUIDStr | None = None


class AuditDecision(BaseModel):
    """Inline gate decision summary for agent_invocation events."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    gate: int = Field(ge=1, le=6)
    verb: str = Field(description="Decision verb (e.g., 'COMMUNICATE', 'AFFECTED', 'SEND_NOW').")
    reason: str = Field(description="Short reason summary. Must not contain PII.")


class AuditMetrics(BaseModel):
    """Optional performance and cost metrics."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    token_count_input: int | None = Field(default=None, ge=0)
    token_count_output: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    latency_ms: int | None = Field(default=None, ge=0)


class AuditError(BaseModel):
    """Error details for failed events. Must not contain PII or stack traces with internal paths."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    code: str = Field(
        description="Machine-readable error code (e.g., 'SCHEMA_VALIDATION_FAILURE')."
    )
    message: str = Field(
        description="Human-readable error message. Must not contain PII or secrets."
    )


class AuditRecord(BaseModel):
    """Append-only audit log entry.

    One record is written for every LLM invocation, tool call, hook firing, HITL action,
    delivery attempt, state transition, policy check, and error. Records are immutable once
    written. No PII anywhere — output_summary is a structured summary, never a raw LLM dump.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    schema_version: str = Field(default="1.0")
    audit_id: UUIDStr = Field(description="UUID v4. Primary key in the audit store.")
    timestamp: AwareDatetime = Field(description="UTC timestamp of the event.")
    event_type: EventType
    change_id: UUIDStr = Field(description="Always populated. The unit of end-to-end traceability.")
    correlation_ids: CorrelationIds | None = Field(
        default=None,
        description="Optional cross-record correlation identifiers.",
    )
    actor: Actor
    action: str = Field(
        description="Short verb describing what the actor did "
        "(e.g., 'invoked', 'completed', 'approved', 'sent')."
    )
    input_hash: str = Field(
        description="SHA-256 hex digest of the serialized input. "
        "Never the raw input — hashing prevents PII from landing in audit records."
    )
    output_summary: str = Field(
        max_length=500,
        description="Structured summary of the action output. Must not dump raw LLM responses "
        "or contain PII, PHI, or secrets.",
    )
    decision: AuditDecision | None = Field(
        default=None,
        description="Inline gate decision summary. Populated for agent_invocation events.",
    )
    metrics: AuditMetrics | None = Field(default=None)
    outcome: AuditOutcome
    error: AuditError | None = Field(
        default=None,
        description="Error details. Populated when outcome is 'failure'.",
    )
