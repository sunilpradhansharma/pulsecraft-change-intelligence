"""Delivery payload schemas — rendered channel-specific content and send outcomes."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class TeamsCardPayload(BaseModel):
    """Rendered Teams adaptive card ready for delivery."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    card_json: dict = Field(description="Adaptive card v1.5 structure as a parsed dict.")
    length_bytes: int = Field(ge=0, description="Byte length of serialized card_json (UTF-8).")


class EmailPayload(BaseModel):
    """Rendered email with plain-text and HTML bodies."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    subject: str = Field(description="Email subject line.")
    body_text: str = Field(description="Plain-text email body.")
    body_html: str = Field(description="HTML email body.")
    headers: dict = Field(default_factory=dict, description="Additional email headers.")


class PushPayload(BaseModel):
    """Rendered push notification. Titles capped at 65 chars, bodies at 240."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    title: str = Field(max_length=65, description="Push notification title. Max 65 characters.")
    body: str = Field(max_length=240, description="Push notification body. Max 240 characters.")


class DigestPayload(BaseModel):
    """Rendered digest combining multiple PersonalizedBriefs into one Markdown document."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    markdown: str = Field(description="Combined digest in Markdown format.")
    item_count: int = Field(ge=0, description="Number of PersonalizedBrief items in this digest.")
    bu_id: str = Field(description="Target BU identifier.")
    digest_date: date = Field(description="Date this digest covers.")


class DeliveryResult(BaseModel):
    """Outcome of a single delivery send attempt."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    delivery_id: str = Field(description="UUID v4 for this delivery attempt.")
    outcome: Literal["sent", "failed", "retriable"] = Field(description="Send outcome.")
    transport_ref: str | None = Field(
        default=None,
        description="Transport reference: file path in dev mode; message-ID in production.",
    )
    error_reason: str | None = Field(
        default=None,
        description="Failure reason if outcome is 'failed' or 'retriable'.",
    )
    sent_at: AwareDatetime | None = Field(
        default=None,
        description="UTC timestamp when the message was sent. None when outcome is not 'sent'.",
    )


class ScheduledDelivery(BaseModel):
    """A delivery scheduled for a future time (HOLD_UNTIL or DIGEST decisions)."""

    model_config = ConfigDict(extra="forbid", frozen=False, str_strip_whitespace=True)

    delivery_id: str = Field(description="UUID v4 for this scheduled delivery.")
    send_at: AwareDatetime = Field(description="UTC timestamp when the delivery should go out.")
    channel: str = Field(description="Target delivery channel.")
    reason: str = Field(description="Why this delivery was scheduled for this time.")
