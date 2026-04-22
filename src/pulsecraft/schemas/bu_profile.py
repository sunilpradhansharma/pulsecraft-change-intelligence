"""BUProfile schema — BU registry configuration, read-only input to BUAtlas."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

BUIdStr = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]*$")]


class Channel(StrEnum):
    """Approved delivery channels."""

    TEAMS = "teams"
    EMAIL = "email"
    PUSH = "push"
    PORTAL_DIGEST = "portal_digest"
    SERVICENOW = "servicenow"


class BUHead(BaseModel):
    """BU head identity and delegate configuration. No contact details."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    name: str = Field(description="Display name of the BU head. Must not be an email address.")
    role: str = Field(description="Organizational role title.")
    delegate_ids: list[str] = Field(
        default_factory=list,
        description="Opaque recipient IDs of named delegates.",
    )


class QuietHours(BaseModel):
    """Quiet hours window during which no push notifications are sent."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    timezone: str = Field(description="IANA timezone identifier (e.g., 'America/Chicago').")
    start: str = Field(
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Quiet hours start time in HH:MM (24-hour, local to timezone).",
    )
    end: str = Field(
        pattern=r"^([01]\d|2[0-3]):[0-5]\d$",
        description="Quiet hours end time in HH:MM (24-hour, local to timezone).",
    )


class Preferences(BaseModel):
    """BU-level notification preferences."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    channels: list[Channel] = Field(
        min_length=1,
        description="Approved delivery channels in preference order.",
    )
    quiet_hours: QuietHours
    digest_opt_in: bool = Field(
        description="Whether this BU has opted into digest-format notifications for P2 items."
    )
    max_notifications_per_week: int | None = Field(
        default=None,
        ge=0,
        description="Optional weekly push-notification cap. Enforced by the rate-limit policy hook.",
    )


class EscalationContact(BaseModel):
    """Escalation contact for unresolved or urgent items. No contact details."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    name: str = Field(description="Display name of the escalation contact.")
    role: str = Field(description="Organizational role.")


class BUProfile(BaseModel):
    """Business Unit configuration — read-only input to BUAtlas.

    Authored as versioned YAML in config/ and validated against bu_profile.schema.json.
    This model contains no PII by contract — all 'name' values are display names only,
    not email addresses or employee IDs.
    """

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    schema_version: str = Field(default="1.0")
    bu_id: BUIdStr = Field(
        description="Stable lowercase BU identifier (e.g., 'immunology'). Unique in registry."
    )
    name: str = Field(description="Human-readable BU display name.")
    head: BUHead
    therapeutic_area: str | None = Field(
        default=None,
        description="Primary therapeutic area. Placeholder in v1; will align with AbbVie BU taxonomy.",
    )
    owned_product_areas: list[str] = Field(
        min_length=1,
        description="Product area identifiers owned by this BU. Must match impact_areas vocabulary.",
    )
    preferences: Preferences
    active_initiatives: list[str] = Field(
        description="Sanitized descriptions of current BU initiatives. Used by BUAtlas gate 4.",
    )
    escalation_contact: EscalationContact
    okrs_current_quarter: list[str] = Field(
        default_factory=list,
        description="Summarized, sanitized OKRs for the current quarter. No confidential targets.",
    )
    historical_notification_feedback_summary: dict[str, Any] | None = Field(
        default=None,
        description="Aggregate stats only — no PII. Exact shape TODO pending feedback-loop implementation.",
    )
