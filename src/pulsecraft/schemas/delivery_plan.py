"""DeliveryPlan schema — PushPilot output + delivery metadata (gate 6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from pulsecraft.schemas.decision import Decision

UUIDStr = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]

BUIdStr = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]*$")]


class DeliveryDecision(StrEnum):
    """Gate 6 delivery decision verbs."""

    SEND_NOW = "send_now"
    HOLD_UNTIL = "hold_until"
    DIGEST = "digest"
    ESCALATE = "escalate"


class Channel(StrEnum):
    """Approved delivery channels."""

    TEAMS = "teams"
    EMAIL = "email"
    PUSH = "push"
    PORTAL_DIGEST = "portal_digest"
    SERVICENOW = "servicenow"


class PolicyViolation(StrEnum):
    """Types of policy violations detected by the pre-delivery hook."""

    QUIET_HOURS = "quiet_hours"
    RATE_LIMIT = "rate_limit"
    UNAPPROVED_CHANNEL = "unapproved_channel"
    RESTRICTED_TERMS = "restricted_terms"
    MLR_SENSITIVE = "mlr_sensitive"
    DEDUPE_CONFLICT = "dedupe_conflict"


class BackoffStrategy(StrEnum):
    """Retry backoff strategies."""

    EXPONENTIAL = "exponential"
    FIXED = "fixed"
    NONE = "none"


class RetryCondition(StrEnum):
    """Conditions that trigger a delivery retry."""

    TRANSIENT_ERROR = "transient_error"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"


class ProducedBy(BaseModel):
    """Producer identity for a DeliveryPlan."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    agent: str = Field(default="pushpilot", pattern="^pushpilot$")
    version: str = Field(description="PushPilot agent version.")


class RecipientDisplay(BaseModel):
    """Display-name attribution for the recipient. No contact details."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    name: str = Field(description="Recipient display name. Must not be an email address.")
    role: str = Field(description="Organizational role title.")


class PolicyCheck(BaseModel):
    """Result of the pre-delivery policy check (executed by deterministic code, not the agent)."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    passed: bool = Field(description="True if all policy checks passed.")
    violations: list[PolicyViolation] = Field(
        default_factory=list,
        description="Specific policy violations detected.",
    )
    reasons: list[str] = Field(
        default_factory=list,
        description="Human-readable explanations per violation. Must not contain PII.",
    )


class RetryPolicy(BaseModel):
    """Delivery retry configuration."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    max_attempts: int = Field(ge=1, description="Maximum delivery attempts including the first.")
    backoff: BackoffStrategy
    retry_on: list[RetryCondition] = Field(description="Error conditions that trigger a retry.")


class DeliveryPlan(BaseModel):
    """PushPilot's gate 6 delivery decision plus deterministic delivery metadata.

    The agent decides the verb and reason. Deterministic code enforces policy
    invariants (quiet hours, rate limits, dedupe) and may override toward a more
    conservative outcome, logging the override as a separate AuditRecord.

    Dedupe key generation: SHA-256 of (change_id + bu_id + recipient_id + message_variant_id),
    where message_variant_id is a stable SHA-256 of the chosen message variant content.
    Keys are stable across replays of the same logical notification.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    schema_version: str = Field(default="1.0")
    delivery_id: UUIDStr = Field(description="UUID v4 for this DeliveryPlan.")
    personalized_brief_id: UUIDStr = Field(description="Traces back to the PersonalizedBrief.")
    change_id: UUIDStr = Field(description="Traces back to the originating ChangeArtifact.")
    bu_id: BUIdStr = Field(description="Target BU registry ID.")
    recipient_id: str = Field(
        description="Opaque recipient identifier. Must not be an email address — "
        "channel adapters resolve contact details separately."
    )
    recipient_display: RecipientDisplay
    produced_at: AwareDatetime = Field(description="UTC timestamp of production.")
    produced_by: ProducedBy = Field(description="PushPilot producer identity and version.")
    decision: DeliveryDecision = Field(description="Gate 6 delivery decision.")
    channel: Channel | None = Field(
        description="Target delivery channel. None when decision is escalate or hold pending resolution."
    )
    scheduled_time: AwareDatetime | None = Field(
        description="UTC delivery time. None when decision is send_now or escalate."
    )
    reason: str = Field(
        description="Required explanation of the gate 6 decision. Must name specific signals. "
        "Must not contain PII or internal secrets."
    )
    dedupe_key: str = Field(
        description="Deterministic dedup key: SHA-256 of (change_id + bu_id + recipient_id + "
        "message_variant_id). Stable across replays. Prevents duplicate deliveries."
    )
    policy_check: PolicyCheck
    retry_policy: RetryPolicy
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="PushPilot's confidence in the gate 6 decision."
    )
    decisions: list[Decision] = Field(description="Gate 6 decision. Typically one entry.")
