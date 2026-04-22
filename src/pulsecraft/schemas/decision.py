"""Decision sub-schema: shared across all agent output contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class DecisionVerb(StrEnum):
    """All gate decision verbs across all agents. One shared enum prevents typo bugs."""

    # Gate 1 — SignalScribe: is this worth communicating?
    COMMUNICATE = "COMMUNICATE"
    ARCHIVE = "ARCHIVE"

    # Gate 2 — SignalScribe: is timing right?
    RIPE = "RIPE"
    HOLD_UNTIL = "HOLD_UNTIL"
    HOLD_INDEFINITE = "HOLD_INDEFINITE"

    # Gate 3 — SignalScribe: is the interpretation good enough to hand off?
    READY = "READY"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"
    UNRESOLVABLE = "UNRESOLVABLE"

    # Gate 4 — BUAtlas: is this BU actually affected?
    AFFECTED = "AFFECTED"
    ADJACENT = "ADJACENT"
    NOT_AFFECTED = "NOT_AFFECTED"

    # Gate 5 — BUAtlas: is the drafted message worth sending?
    WORTH_SENDING = "WORTH_SENDING"
    WEAK = "WEAK"
    NOT_WORTH = "NOT_WORTH"

    # Gate 6 — PushPilot: is now the right time to send?
    SEND_NOW = "SEND_NOW"
    DIGEST = "DIGEST"

    # Cross-gate: any agent may escalate to HITL when confidence is too low
    ESCALATE = "ESCALATE"


class DecisionAgent(BaseModel):
    """Identity of the agent that made a gate decision."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    name: str = Field(description="Agent name.", pattern="^(signalscribe|buatlas|pushpilot)$")
    version: str = Field(description="Agent version string at time of decision.")


class Decision(BaseModel):
    """A single gate decision, carried in the decisions[] array of agent output contracts.

    Enables full decision-chain replay: given a change_id, the entire sequence of
    gate decisions can be reconstructed from the decisions[] arrays across contracts.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    gate: int = Field(ge=1, le=6, description="Gate number (1-6) that this decision resolves.")
    verb: DecisionVerb = Field(description="The decision verb. See DecisionVerb for semantics.")
    reason: str = Field(
        max_length=1000,
        description="Plain-English reason citing the specific signals that drove this decision. "
        "Must not contain PII or internal secrets.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Agent confidence in this decision. 0 = no confidence, 1 = fully certain. "
        "See decision criteria doc for threshold semantics per gate.",
    )
    decided_at: AwareDatetime = Field(
        description="UTC timestamp when this decision was made. Naive datetimes are rejected."
    )
    agent: DecisionAgent = Field(description="Agent identity and version.")
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Verb-specific extra data. HOLD_UNTIL carries {date, trigger}; "
        "NEED_CLARIFICATION carries {questions: [str]}.",
    )
