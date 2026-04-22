"""ChannelPolicy schema — approved channels, priority routing, dedupe, digest config."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApprovedChannels(BaseModel):
    """Approved delivery channels: global list and per-channel BU restrictions."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    # "global" is a Python keyword; alias maps the YAML key to this field name
    global_channels: list[str] = Field(
        alias="global",
        description="Channels approved for any BU unless overridden.",
    )
    restricted: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Channels approved only for specific BUs; maps channel → [bu_id, ...].",
    )


class ChannelSelectionRule(BaseModel):
    """A single priority-based channel routing rule; first match wins."""

    model_config = ConfigDict(extra="forbid")

    when: dict[str, Any] = Field(
        description="Condition keys (priority, recipient_digest_opt_in, etc.)."
    )
    channel: str = Field(description="Primary delivery channel for this rule.")
    also_send_to: list[str] = Field(
        default_factory=list,
        description="Additional channels to send to (e.g., email backup for P0 Teams alert).",
    )


class ChannelSelectionDefault(BaseModel):
    """Fallback channel when no routing rule matches."""

    model_config = ConfigDict(extra="forbid")

    channel: str


class DedupeConfig(BaseModel):
    """Deduplication window and key configuration."""

    model_config = ConfigDict(extra="forbid")

    window_hours: int = Field(
        gt=0, description="Hours within which duplicate messages are suppressed."
    )
    key_components: list[str] = Field(description="Fields that compose the dedupe key.")


class DigestConfig(BaseModel):
    """Digest bundling configuration for P2 notifications."""

    model_config = ConfigDict(extra="forbid")

    cadence: str = Field(description="Digest delivery cadence (e.g., 'daily').")
    send_time_recipient_local: str = Field(description="Local send time in HH:MM format.")
    max_items_per_digest: int = Field(gt=0, description="Maximum items bundled in a single digest.")
    priority_filter: list[str] = Field(description="Priority levels eligible for digest delivery.")


class ChannelPolicy(BaseModel):
    """Channel delivery policy — approved channels, routing rules, dedupe, digest config.

    Enforced in code (pre-delivery hook). Agents cannot override these values.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    schema_version: str = Field(default="1.0")
    approved_channels: ApprovedChannels
    channel_selection_rules: list[ChannelSelectionRule]
    channel_selection_default: ChannelSelectionDefault
    dedupe: DedupeConfig
    digest: DigestConfig
